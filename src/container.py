from typing import Dict, Type, TypeVar
from threading import RLock

T = TypeVar('T')


class Container:
    """Thread-safe generic object container for dependency management."""
    _instances: Dict[Type, object] = {}
    _lock = RLock()

    @classmethod
    def get(cls, obj_type: Type[T]) -> T:
        """Get a registered instance by type."""
        with cls._lock:
            if obj_type not in cls._instances:
                raise RuntimeError(f"{obj_type.__name__} not initialized. Call Container.set() first.")
            return cls._instances[obj_type]
    
    @classmethod
    def set(cls, obj_type: Type[T], instance: T) -> None:
        """Register an instance by type."""
        with cls._lock:
            cls._instances[obj_type] = instance

    @classmethod
    def reset(cls) -> None:
        """Reset container (primarily for testing)."""
        with cls._lock:
            cls._instances.clear()
