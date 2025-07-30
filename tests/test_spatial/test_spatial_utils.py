"""
Tests for the spatial utilities (formerly CMR client) and related classes.
"""

import numpy as np
import pytest

from nsidc.metgen.lab import (
    PolygonComparator,
    UMMGParser,
    sanitize_granule_ur,
)

# CMRClient tests removed - functionality replaced by earthaccess
# The following tests have been removed as they test the deprecated CMRClient class:
# - test_client_initialization
# - test_query_granules
# - test_get_umm_json
# - test_get_random_granules


class TestUMMGParserFixtures:
    """Test fixtures for UMMGParser tests."""

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
        assert feature["properties"]["source"] == "CMR UMM-G"
        assert feature["properties"]["polygon_type"] == "GPolygon"

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
            "cmr_area",
            "generated_area",
            "cmr_vertices",
            "generated_vertices",
            "cmr_coverage_by_generated",
            "generated_coverage_by_cmr",
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
        assert "data_coverage_improvement" in metrics

        # Coverage should be between 0 and 1
        assert 0 <= metrics["cmr_data_coverage"] <= 1
        assert 0 <= metrics["generated_data_coverage"] <= 1

    def test_compare_empty_polygons(self):
        """Test handling of empty polygons."""
        empty_geojson = {"type": "FeatureCollection", "features": []}

        metrics = PolygonComparator.compare(empty_geojson, empty_geojson)

        assert "error" in metrics  # Empty polygons result in error
        assert metrics["error"] == "Empty polygon data"


class TestUtilityFunctions:
    """Test utility functions."""

    def test_sanitize_granule_ur(self):
        """Test granule UR sanitization."""
        # Test various problematic characters
        test_cases = [
            ("GRANULE_001.TXT", "GRANULE_001.TXT"),
            ("GRANULE/WITH/SLASHES.TXT", "GRANULE_WITH_SLASHES.TXT"),
            ("GRANULE:WITH:COLONS.TXT", "GRANULE_WITH_COLONS.TXT"),
            ("GRANULE WITH SPACES.TXT", "GRANULE WITH SPACES.TXT"),  # Spaces preserved
            ("GRANULE*WITH*STARS.TXT", "GRANULE_WITH_STARS.TXT"),
        ]

        for input_ur, expected in test_cases:
            assert sanitize_granule_ur(input_ur) == expected
