import asyncio
import time

# ============================================
# ACTIVE CALLBACKS
# ============================================

active_callbacks = {}

# ============================================
# ACQUIRE LOCK
# ============================================

async def acquire_lock(
    user_id: int,
    action: str,
    timeout: int = 5
):

    key = f"{user_id}:{action}"

    current_time = time.time()

    # ============================================
    # LOCK EXISTS
    # ============================================

    if key in active_callbacks:

        lock_time = active_callbacks[key]

        # lock ще активний
        if current_time - lock_time < timeout:
            return False

    # ============================================
    # CREATE LOCK
    # ============================================

    active_callbacks[key] = current_time

    return True

# ============================================
# RELEASE LOCK
# ============================================

async def release_lock(
    user_id: int,
    action: str
):

    key = f"{user_id}:{action}"

    if key in active_callbacks:
        del active_callbacks[key]