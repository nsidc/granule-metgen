"""
Tests for the CMR client and related classes.
"""

from unittest.mock import Mock, patch

import numpy as np
import pytest
from nsidc.metgen.spatial import (
    CMRClient,
    PolygonComparator,
    UMMGParser,
    sanitize_granule_ur,
)


class TestCMRClient:
    """Test suite for CMRClient."""

    @pytest.fixture
    def client(self):
        """Create a CMRClient instance."""
        return CMRClient(token="test-token")

    @pytest.fixture
    def mock_granule_response(self):
        """Mock CMR granule search response."""
        return {
            "feed": {
                "entry": [
                    {
                        "id": "G1234567890-PROVIDER",
                        "title": "TEST_GRANULE_001.TXT",
                        "producer_granule_id": "TEST_GRANULE_001.TXT",
                        "time_start": "2023-01-01T00:00:00.000Z",
                        "time_end": "2023-01-01T01:00:00.000Z",
                    }
                ]
            }
        }

    @pytest.fixture
    def mock_umm_response(self):
        """Mock UMM-G response."""
        return {
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
            },
            "RelatedUrls": [
                {
                    "URL": "https://example.com/data/TEST_GRANULE_001.TXT",
                    "Type": "GET DATA",
                }
            ],
        }

    def test_client_initialization(self):
        """Test CMRClient initialization."""
        # With token
        client = CMRClient(token="test-token")
        assert client.session.headers["Authorization"] == "Bearer test-token"

        # Without token
        client = CMRClient()
        assert "Authorization" not in client.session.headers

    @patch("requests.Session.get")
    def test_query_granules(self, mock_get, client, mock_granule_response):
        """Test granule querying."""
        mock_response = Mock()
        mock_response.json.return_value = mock_granule_response
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"cmr-hits": "1"}  # Add required header
        mock_get.return_value = mock_response

        granules = client.query_granules("TEST_COLLECTION", provider="TEST_PROVIDER")

        assert len(granules) == 1
        assert granules[0]["title"] == "TEST_GRANULE_001.TXT"

        # Check that correct parameters were used
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        # Check the params dictionary directly
        assert call_args[1]["params"]["short_name"] == "TEST_COLLECTION"
        assert call_args[1]["params"]["provider"] == "TEST_PROVIDER"

    @patch("requests.Session.get")
    def test_get_umm_json(self, mock_get, client, mock_umm_response):
        """Test UMM-G retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = mock_umm_response
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        umm_json = client.get_umm_json("G1234567890-PROVIDER")

        assert "SpatialExtent" in umm_json
        assert "RelatedUrls" in umm_json

    @patch("requests.Session.get")
    def test_get_random_granules(self, mock_get, client, mock_granule_response):
        """Test random granule selection."""
        # Mock response with multiple granules
        multi_response = {
            "feed": {
                "entry": [
                    {
                        "id": f"G123456789{i}-PROVIDER",
                        "title": f"TEST_GRANULE_{i:03d}.TXT",
                        "time_start": f"2023-{i:02d}-01T00:00:00.000Z",
                    }
                    for i in range(1, 11)
                ]
            }
        }

        mock_response = Mock()
        mock_response.json.return_value = multi_response
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"cmr-hits": "10"}  # Add required header
        mock_get.return_value = mock_response

        # Get random granules
        random_granules = client.get_random_granules("TEST_COLLECTION", count=3)

        assert len(random_granules) == 3
        # Check that we got different granules (with high probability)
        titles = [g["title"] for g in random_granules]
        assert len(set(titles)) == 3


class TestUMMGParser:
    """Test suite for UMMGParser."""

    def test_extract_polygons(self):
        """Test polygon extraction from UMM-G."""
        umm_json = {
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

        geojson = UMMGParser.extract_polygons(umm_json, "TEST_GRANULE")

        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 1

        feature = geojson["features"][0]
        assert feature["geometry"]["type"] == "Polygon"
        assert len(feature["geometry"]["coordinates"][0]) == 5
        assert feature["properties"]["granule_ur"] == "TEST_GRANULE"

    def test_extract_polygons_no_geometry(self):
        """Test handling of UMM-G without geometry."""
        umm_json = {"SpatialExtent": {}}

        geojson = UMMGParser.extract_polygons(umm_json, "TEST_GRANULE")

        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 0

    def test_extract_data_urls(self):
        """Test data URL extraction."""
        umm_json = {
            "RelatedUrls": [
                {
                    "URL": "https://example.com/browse/image.png",
                    "Type": "GET RELATED VISUALIZATION",
                },
                {"URL": "https://example.com/data/file.txt", "Type": "GET DATA"},
                {"URL": "https://example.com/data/file2.h5", "Type": "GET DATA"},
            ]
        }

        urls = UMMGParser.extract_data_urls(umm_json)

        assert len(urls) == 2
        assert all("data" in url for url in urls)
        assert not any("browse" in url for url in urls)

    def test_find_data_file(self):
        """Test finding correct data file by extension."""
        urls = [
            "https://example.com/data/file.png",
            "https://example.com/data/file.txt",
            "https://example.com/data/file.h5",
            "https://example.com/data/file.pdf",
        ]

        # Find text file
        txt_file = UMMGParser.find_data_file(urls, [".txt", ".TXT"])
        assert txt_file == "https://example.com/data/file.txt"

        # Find HDF5 file
        h5_file = UMMGParser.find_data_file(urls, [".h5", ".hdf5"])
        assert h5_file == "https://example.com/data/file.h5"

        # No matching file
        no_file = UMMGParser.find_data_file(urls, [".nc", ".netcdf"])
        assert no_file is None


class TestPolygonComparator:
    """Test suite for PolygonComparator."""

    @pytest.fixture
    def cmr_polygon(self):
        """Create a sample CMR polygon GeoJSON."""
        return {
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
                    "properties": {"source": "CMR"},
                }
            ],
        }

    @pytest.fixture
    def generated_polygon(self):
        """Create a sample generated polygon GeoJSON."""
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-120.1, 34.9],
                                [-118.9, 34.9],
                                [-118.9, 36.1],
                                [-120.1, 36.1],
                                [-120.1, 34.9],
                            ]
                        ],
                    },
                    "properties": {"source": "Generated"},
                }
            ],
        }

    def test_compare_polygons(self, cmr_polygon, generated_polygon):
        """Test polygon comparison metrics."""
        metrics = PolygonComparator.compare(cmr_polygon, generated_polygon)

        # Check that all expected metrics are present
        expected_metrics = [
            "iou",
            "area_ratio",
            "cmr_area_deg2",
            "generated_area_deg2",
            "cmr_vertices",
            "generated_vertices",
            "cmr_covered_by_generated",
            "generated_covered_by_cmr",
        ]

        for metric in expected_metrics:
            assert metric in metrics

        # Check metric values are reasonable
        assert 0 <= metrics["iou"] <= 1
        assert metrics["area_ratio"] > 0
        assert (
            metrics["cmr_vertices"] == 4
        )  # Rectangle has 4 vertices (closing point not counted)
        assert metrics["generated_vertices"] == 4

    def test_compare_with_data_coverage(self, cmr_polygon, generated_polygon):
        """Test comparison with data coverage metrics."""
        # Create sample data points
        lon = np.random.uniform(-120, -119, 100)
        lat = np.random.uniform(35, 36, 100)
        data_points = np.column_stack((lon, lat))

        metrics = PolygonComparator.compare(
            cmr_polygon, generated_polygon, data_points=data_points
        )

        # Should have additional coverage metrics
        assert "cmr_data_coverage" in metrics
        assert "generated_data_coverage" in metrics
        assert "data_coverage_ratio" in metrics

        # Coverage should be between 0 and 1
        assert 0 <= metrics["cmr_data_coverage"] <= 1
        assert 0 <= metrics["generated_data_coverage"] <= 1

    def test_compare_empty_polygons(self):
        """Test handling of empty polygons."""
        empty_geojson = {"type": "FeatureCollection", "features": []}

        metrics = PolygonComparator.compare(empty_geojson, empty_geojson)

        assert metrics["iou"] == 0
        assert metrics["cmr_vertices"] == 0
        assert metrics["generated_vertices"] == 0


class TestUtilityFunctions:
    """Test utility functions."""

    def test_sanitize_granule_ur(self):
        """Test granule UR sanitization."""
        # Test various problematic characters
        test_cases = [
            ("GRANULE_001.TXT", "GRANULE_001.TXT"),
            ("GRANULE/WITH/SLASHES.TXT", "GRANULE_WITH_SLASHES.TXT"),
            ("GRANULE:WITH:COLONS.TXT", "GRANULE_WITH_COLONS.TXT"),
            ("GRANULE WITH SPACES.TXT", "GRANULE_WITH_SPACES.TXT"),
            ("GRANULE*WITH*STARS.TXT", "GRANULE_WITH_STARS.TXT"),
        ]

        for input_ur, expected in test_cases:
            assert sanitize_granule_ur(input_ur) == expected
