import pytest

from src.container import Container
from src.database.data_connection import Database


class TestContainer:
    """Tests for Container singleton object management."""

    def setup_method(self):
        Container.reset()

    def teardown_method(self):
        Container.reset()

    def test_set_registers_instance_by_type(self):
        # Arrange
        class ServiceA:
            pass
        service_a = ServiceA()
        
        # Act
        Container.set(ServiceA, service_a)
        
        # Assert
        assert Container.get(ServiceA) is service_a

    def test_get_raises_error_when_not_initialized(self):
        # Arrange
        Container.reset()
        
        # Act & Assert
        with pytest.raises(RuntimeError, match="Database not initialized"):
            Container.get(Database)

    def test_reset_clears_registered_instances(self):
        # Arrange
        class ServiceA:
            pass

        Container.set(ServiceA, ServiceA())
        
        # Act
        Container.reset()
        
        # Assert
        with pytest.raises(RuntimeError):
            Container.get(Database)

    def test_can_register_and_retrieve_multiple_types(self):
        # Arrange
        class ServiceA:
            pass
        
        class ServiceB:
            pass
        
        service_a = ServiceA()
        service_b = ServiceB()
        
        # Act
        Container.set(ServiceA, service_a)
        Container.set(ServiceB, service_b)
        
        # Assert
        assert Container.get(ServiceA) is service_a
        assert Container.get(ServiceB) is service_b

