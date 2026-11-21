from pow51sim.core.blockchain import Blockchain


def is_confirmed(public: Blockchain, payment_height: int, required: int) -> bool:
    return public.height - payment_height >= required
