#!/usr/bin/env python3
"""
Delete all chores in the test environment.

This script:
1. Lists all existing chores
2. Deletes each chore one by one
3. Provides detailed logging of the process
4. Verifies final state
"""

import asyncio
import logging
import sys
from datetime import datetime

from donetick_mcp.client import DonetickClient

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'chore_deletion_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """Delete all chores in the test environment."""

    print("=" * 80)
    print("CHORE DELETION UTILITY - v0.2.0")
    print("=" * 80)
    print()

    client = DonetickClient()

    try:
        # Step 1: Authenticate
        print("📋 Step 1: Authentication")
        print("-" * 80)
        await client.login()
        logger.info("Successfully authenticated with Donetick API")
        print("✓ Authenticated successfully")
        print()

        # Step 2: List all chores
        print("📋 Step 2: Listing All Chores")
        print("-" * 80)
        chores = await client.list_chores()
        logger.info(f"Found {len(chores)} chores in the system")

        if len(chores) == 0:
            print("✓ No chores found - nothing to delete")
            print()
            return 0

        print(f"Found {len(chores)} chores to delete:")
        print()

        # Display all chores with details
        for i, chore in enumerate(chores, 1):
            print(f"  {i}. ID: {chore.id}")
            print(f"     Name: {chore.name}")
            print(f"     Created: {chore.createdAt}")
            print(f"     Active: {chore.isActive}")
            print(f"     Assigned To: {chore.assignedTo}")
            logger.info(f"Chore {chore.id}: {chore.name}")
            print()

        # Step 3: Confirm deletion
        print("📋 Step 3: Deletion Process")
        print("-" * 80)
        print(f"⚠️  About to delete {len(chores)} chores")
        print()

        # Delete each chore
        deleted_count = 0
        failed_deletions = []

        for i, chore in enumerate(chores, 1):
            try:
                print(f"[{i}/{len(chores)}] Deleting chore {chore.id}: {chore.name[:50]}...")
                logger.info(f"Attempting to delete chore {chore.id}")

                result = await client.delete_chore(chore.id)

                if result:
                    deleted_count += 1
                    logger.info(f"✓ Successfully deleted chore {chore.id}")
                    print(f"    ✓ Deleted")
                else:
                    logger.warning(f"✗ Failed to delete chore {chore.id} - returned False")
                    failed_deletions.append((chore.id, chore.name, "Returned False"))
                    print(f"    ✗ Failed (returned False)")

            except Exception as e:
                logger.error(f"✗ Error deleting chore {chore.id}: {e}", exc_info=True)
                failed_deletions.append((chore.id, chore.name, str(e)))
                print(f"    ✗ Error: {e}")

            print()

        # Step 4: Verify deletion
        print("📋 Step 4: Verification")
        print("-" * 80)
        remaining_chores = await client.list_chores()
        logger.info(f"Verification: {len(remaining_chores)} chores remaining")

        print(f"Chores remaining after deletion: {len(remaining_chores)}")
        print()

        # Step 5: Summary
        print("=" * 80)
        print("DELETION SUMMARY")
        print("=" * 80)
        print()
        print(f"Total chores found: {len(chores)}")
        print(f"Successfully deleted: {deleted_count}")
        print(f"Failed deletions: {len(failed_deletions)}")
        print(f"Remaining chores: {len(remaining_chores)}")
        print()

        if failed_deletions:
            print("Failed Deletions:")
            for chore_id, name, error in failed_deletions:
                print(f"  - Chore {chore_id}: {name}")
                print(f"    Error: {error}")
                logger.error(f"Failed deletion - Chore {chore_id}: {error}")
            print()

        if remaining_chores:
            print("Remaining Chores:")
            for chore in remaining_chores:
                print(f"  - ID {chore.id}: {chore.name}")
                logger.warning(f"Remaining chore - ID {chore.id}: {chore.name}")
            print()

        # Log file location
        log_files = [h.baseFilename for h in logger.handlers if isinstance(h, logging.FileHandler)]
        if log_files:
            print(f"📄 Detailed logs saved to: {log_files[0]}")
            print()

        # Final status
        if len(remaining_chores) == 0 and deleted_count == len(chores):
            print("✅ SUCCESS: All chores deleted successfully!")
            logger.info("Deletion process completed successfully - all chores removed")
            return 0
        elif len(failed_deletions) > 0:
            print("⚠️  PARTIAL SUCCESS: Some chores could not be deleted")
            logger.warning("Deletion process completed with errors")
            return 1
        else:
            print("✅ COMPLETED: Deletion process finished")
            logger.info("Deletion process completed")
            return 0

    except Exception as e:
        logger.error(f"Fatal error during deletion process: {e}", exc_info=True)
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        await client.close()
        logger.info("Client connection closed")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
