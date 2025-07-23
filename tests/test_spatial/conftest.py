"""
Pytest configuration and fixtures for spatial module tests.
"""

from pathlib import Path

import numpy as np
import pytest


@pytest.fixture(scope="session")
def test_data_dir():
    """Get the test data directory."""
    return Path(__file__).parent / "test_data"


@pytest.fixture
def sample_coordinates():
    """Generate various sample coordinate sets for testing."""
    return {
        "linear": {
            "lon": np.linspace(-120, -119, 100),
            "lat": np.linspace(35, 36, 100),
        },
        "curved": {
            "lon": -120 + 0.5 * np.sin(np.linspace(0, 2 * np.pi, 200)),
            "lat": 35 + 0.5 * np.cos(np.linspace(0, 2 * np.pi, 200)),
        },
        "sparse": {
            "lon": np.array([-120, -119.5, -119, -118.5]),
            "lat": np.array([35, 35.2, 35.4, 35.6]),
        },
        "dense": {
            "lon": np.random.normal(-120, 0.1, 5000),
            "lat": np.random.normal(35, 0.1, 5000),
        },
    }


@pytest.fixture
def cmr_polygon_examples():
    """Example CMR polygons in different formats."""
    return {
        "simple": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [[-120, 35], [-119, 35], [-119, 36], [-120, 36], [-120, 35]]
                        ],
                    },
                    "properties": {"source": "CMR", "vertices": 5},
                }
            ],
        },
        "complex": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-120, 35],
                                [-119.5, 35],
                                [-119, 35.2],
                                [-118.8, 35.5],
                                [-119, 36],
                                [-119.5, 36],
                                [-120, 35.8],
                                [-120, 35],
                            ]
                        ],
                    },
                    "properties": {"source": "CMR", "vertices": 8},
                }
            ],
        },
    }


@pytest.fixture
def mock_cmr_client(monkeypatch):
    """Create a mock CMR client that doesn't make real API calls."""
    from unittest.mock import MagicMock, Mock

    mock_client = Mock()
    mock_client.session = MagicMock()
    mock_client.base_url = "https://cmr.earthdata.nasa.gov"

    # Mock query_granules
    mock_client.query_granules.return_value = [
        {
            "id": "G1234567890-MOCK",
            "title": "MOCK_GRANULE_001.TXT",
            "time_start": "2023-01-01T00:00:00Z",
        }
    ]

    # Mock get_umm_json
    mock_client.get_umm_json.return_value = {
        "SpatialExtent": {
            "HorizontalSpatialDomain": {
                "Geometry": {
                    "GPolygons": [
                        {
                            "Boundary": {
                                "Points": [
                                    {"Longitude": -120, "Latitude": 35},
                                    {"Longitude": -119, "Latitude": 35},
                                    {"Longitude": -119, "Latitude": 36},
                                    {"Longitude": -120, "Latitude": 36},
                                    {"Longitude": -120, "Latitude": 35},
                                ]
                            }
                        }
                    ]
                }
            }
        }
    }

    return mock_client


@pytest.fixture
def performance_timer():
    """Simple performance timer for tests."""
    import time

    class Timer:
        def __init__(self):
            self.times = {}

        def start(self, name):
            self.times[name] = time.time()

        def stop(self, name):
            if name in self.times:
                elapsed = time.time() - self.times[name]
                del self.times[name]
                return elapsed
            return None

    return Timer()


# Test markers
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
