#!/usr/bin/env python3
"""
Tasky Bot-Only Launcher – Simple, Direct Execution

Use this script for quick testing or when you only need the Discord bot.
For production with web dashboard integration, use entrypoint.py instead.

Usage:
    python run_bot.py
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv


# Resolve the file from this script so the launch command can be run anywhere.
# Override empty inherited variables, which would otherwise hide valid .env values.
ENV_FILE = Path(__file__).resolve().parent / ".env"
ENV_FILE_LOADED = load_dotenv(ENV_FILE, override=True, encoding="utf-8-sig")

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENVIRONMENT VALIDATION
# ============================================================================

def check_env() -> None:
    """Quick environment validation."""
    load_dotenv()
    logger.info("Environment file %s: %s", ENV_FILE, "loaded" if ENV_FILE_LOADED else "not found or empty")
    required = ["TOKEN", "GEMINI_API_KEY"]
    missing = [var for var in required if not os.getenv(var)]
    
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        logger.error("Please create a .env file with TOKEN and GEMINI_API_KEY")
        sys.exit(1)
    
    logger.info("✓ Environment validated")


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    """Main entry point."""
    try:
        # Validate environment
        check_env()
        
        # Import and run bot
        logger.info("Starting Tasky Discord Bot...")
        from src.bot.main import main as bot_main
        
        bot_main()
    
    except ModuleNotFoundError as e:
        logger.error(f"Import error: {e}")
        logger.error("Make sure all dependencies are installed: pip install -r requirements.txt")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
