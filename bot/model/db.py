from audino import HealthTracker


class Database:

    def __init__(self, *, health_tracker: HealthTracker) -> None:
        self.health_tracker = health_tracker
