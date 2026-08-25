#!/usr/bin/env python3
"""
Tasky Entrypoint – Unified Bot & Web Server Launcher

This script handles:
- Environment validation and early-exit on missing credentials
- Concurrent Discord bot and optional Flask web server execution
- Graceful shutdown (SIGTERM/SIGINT handling)
- Comprehensive logging setup
- Database initialization and health checks
- Clean startup/teardown sequencing
"""

import os
import sys
import logging
import asyncio
import signal
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv


# Resolve the file from this script so the launch command can be run anywhere.
# Override empty inherited variables, which would otherwise hide valid .env values.
ENV_FILE = Path(__file__).resolve().parent / ".env"
ENV_FILE_LOADED = load_dotenv(ENV_FILE, override=True, encoding="utf-8-sig")

# ============================================================================
# CONFIGURATION & LOGGING SETUP
# ============================================================================

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = logging.INFO

# Root logger configuration
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENVIRONMENT VALIDATION
# ============================================================================

def validate_environment() -> None:
    """
    Validates that all required environment variables are set.
    Exits immediately with a helpful error message if any are missing.
    """
    load_dotenv()
    logger.info("Environment file %s: %s", ENV_FILE, "loaded" if ENV_FILE_LOADED else "not found or empty")

    required_vars = {
        "TOKEN": "Discord bot token",
        "GEMINI_API_KEY": "Google Gemini API key",
    }
    
    optional_vars = {
        "GEMINI_MODEL": "gemini-2.5-flash",
        "FLASK_DEBUG": "False",
        "LOG_LEVEL": "INFO",
    }
    
    missing = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing.append(f"  • {var}: {description}")
    
    if missing:
        logger.error("=" * 70)
        logger.error("STARTUP FAILED: Missing required environment variables:")
        for item in missing:
            logger.error(item)
        logger.error("=" * 70)
        logger.error("Create a .env file in the root directory with these variables.")
        logger.error("See README.md for details.")
        sys.exit(1)
    
    # Log optional vars that will be used
    logger.info("Environment validation passed ✓")
    logger.info(f"Using Gemini model: {os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')}")


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

async def initialize_database() -> None:
    """
    Initializes the SQLite database with proper schema and WAL mode.
    This is a prerequisite for both the bot and web server.
    """
    try:
        from src.shared.database import Database
        from src.shared.config import DB_PATH
        
        logger.info(f"Initializing database at {DB_PATH}...")
        db = Database(db_path=DB_PATH)
        await db.initialize_db()
        logger.info("Database initialization successful ✓")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


# ============================================================================
# BOT MANAGEMENT
# ============================================================================

class BotManager:
    """Manages the Discord bot lifecycle."""
    
    def __init__(self):
        self.bot_task: Optional[asyncio.Task] = None
        self.bot = None
    
    async def start(self) -> None:
        """Starts the Discord bot in a background task."""
        try:
            from src.bot.main import client, TOKEN
            
            self.bot = client
            logger.info("Starting Discord bot...")
            
            # Run the bot in the background
            self.bot_task = asyncio.create_task(self._run_bot())
            
            # Give the bot a moment to connect
            await asyncio.sleep(2)
            logger.info("Discord bot startup initiated ✓")
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            raise
    
    async def _run_bot(self) -> None:
        """Runs the Discord bot (blocking until disconnect)."""
        try:
            from src.bot.main import client, TOKEN
            await client.start(TOKEN)
        except Exception as e:
            logger.error(f"Bot encountered an error: {e}")
            raise
    
    async def stop(self) -> None:
        """Stops the Discord bot gracefully."""
        if self.bot:
            try:
                logger.info("Stopping Discord bot...")
                await self.bot.close()
                if self.bot_task:
                    await asyncio.wait_for(self.bot_task, timeout=5.0)
                logger.info("Discord bot stopped ✓")
            except asyncio.TimeoutError:
                logger.warning("Bot did not stop within timeout, canceling...")
                if self.bot_task:
                    self.bot_task.cancel()
            except Exception as e:
                logger.error(f"Error stopping bot: {e}")


# ============================================================================
# WEB SERVER MANAGEMENT (Optional)
# ============================================================================

class WebServerManager:
    """Manages the optional Flask web server."""
    
    def __init__(self, enable: bool = True):
        self.enable = enable
        self.app = None
        self.server_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Starts the Flask web server in a background thread."""
        if not self.enable:
            logger.info("Web server disabled (no src/web/app.py found)")
            return
        
        try:
            # Check if web app exists
            try:
                from src.web.app import app
                self.app = app
            except ModuleNotFoundError:
                logger.warning("Web server not available (src/web/app.py not found)")
                self.enable = False
                return
            
            logger.info("Starting web server on 0.0.0.0:5000...")
            
            # Run Flask in a thread pool to avoid blocking the async loop
            loop = asyncio.get_event_loop()
            self.server_task = loop.create_task(self._run_flask())
            
            await asyncio.sleep(1)
            logger.info("Web server startup initiated ✓")
        except Exception as e:
            logger.error(f"Failed to start web server: {e}")
            # Don't exit if web server fails – bot should continue
    
    async def _run_flask(self) -> None:
        """Runs Flask in a background thread."""
        try:
            import threading
            
            def run_app():
                self.app.run(
                    host="0.0.0.0",
                    port=5000,
                    debug=os.getenv("FLASK_DEBUG", "False").lower() == "true",
                    use_reloader=False,  # Important: disable reloader in threaded mode
                )
            
            thread = threading.Thread(target=run_app, daemon=True)
            thread.start()
            
            # Keep the task alive
            while True:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Flask server error: {e}")
    
    async def stop(self) -> None:
        """Stops the Flask web server gracefully."""
        if self.server_task:
            try:
                logger.info("Stopping web server...")
                self.server_task.cancel()
                await asyncio.wait_for(self.server_task, timeout=2.0)
            except asyncio.CancelledError:
                pass
            except asyncio.TimeoutError:
                logger.warning("Web server did not stop within timeout")
            except Exception as e:
                logger.error(f"Error stopping web server: {e}")


# ============================================================================
# MAIN APPLICATION
# ============================================================================

class TaskyApplication:
    """Main application orchestrator."""
    
    def __init__(self, enable_web: bool = True):
        self.bot_manager = BotManager()
        self.web_manager = WebServerManager(enable=enable_web)
        self.shutdown_event = asyncio.Event()
    
    async def start(self) -> None:
        """Starts all components."""
        logger.info("=" * 70)
        logger.info("TASKY STARTING UP")
        logger.info("=" * 70)
        
        try:
            # Initialize database first
            await initialize_database()
            
            # Start bot
            await self.bot_manager.start()
            
            # Start optional web server
            await self.web_manager.start()
            
            logger.info("=" * 70)
            logger.info("TASKY IS RUNNING")
            logger.info("=" * 70)
        except Exception as e:
            logger.error(f"Startup failed: {e}")
            await self.shutdown()
            sys.exit(1)
    
    async def wait_for_shutdown(self) -> None:
        """Waits for shutdown signal."""
        await self.shutdown_event.wait()
    
    async def shutdown(self) -> None:
        """Gracefully shuts down all components."""
        logger.info("=" * 70)
        logger.info("TASKY SHUTTING DOWN")
        logger.info("=" * 70)
        
        try:
            # Stop in reverse order of startup
            await self.web_manager.stop()
            await self.bot_manager.stop()
            
            logger.info("=" * 70)
            logger.info("TASKY SHUT DOWN COMPLETE")
            logger.info("=" * 70)
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        finally:
            self.shutdown_event.set()


# ============================================================================
# SIGNAL HANDLING
# ============================================================================

def setup_signal_handlers(app: TaskyApplication) -> None:
    """Sets up SIGTERM and SIGINT handlers for graceful shutdown."""
    
    def handle_signal(sig_num, frame):
        signal_name = signal.Signals(sig_num).name
        logger.info(f"Received signal: {signal_name}")
        asyncio.create_task(app.shutdown())
    
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)


# ============================================================================
# ENTRY POINT
# ============================================================================

async def main() -> None:
    """Main async entry point."""
    # Validate environment
    validate_environment()
    
    # Create application
    app = TaskyApplication(enable_web=True)
    
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers(app)
    
    # Start all components
    await app.start()
    
    # Wait for shutdown signal
    try:
        await app.wait_for_shutdown()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Exiting...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
