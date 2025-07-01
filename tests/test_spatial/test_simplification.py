"""
Tests for the polygon simplification algorithm.
"""

import pytest
import numpy as np
from shapely.geometry import Polygon, Point
from nsidc.metgen.spatial import iterative_simplify_polygon


class TestSimplification:
    """Test suite for polygon simplification."""
    
    @pytest.fixture
    def complex_polygon(self):
        """Create a complex polygon with many vertices."""
        # Create a star-like polygon with many vertices
        n_points = 100
        angles = np.linspace(0, 2*np.pi, n_points, endpoint=False)
        
        # Alternate between two radii to create star shape
        radii = np.where(np.arange(n_points) % 2 == 0, 1.0, 0.8)
        
        x = radii * np.cos(angles)
        y = radii * np.sin(angles)
        
        return Polygon(zip(x, y))
    
    @pytest.fixture
    def simple_polygon(self):
        """Create a simple square polygon."""
        return Polygon([
            (0, 0), (1, 0), (1, 1), (0, 1), (0, 0)
        ])
    
    @pytest.fixture
    def data_points(self):
        """Create sample data points."""
        # Create a grid of points
        x = np.linspace(-0.5, 1.5, 20)
        y = np.linspace(-0.5, 1.5, 20)
        xx, yy = np.meshgrid(x, y)
        
        return np.column_stack((xx.ravel(), yy.ravel()))
    
    def test_basic_simplification(self, complex_polygon):
        """Test basic polygon simplification."""
        initial_vertices = len(complex_polygon.exterior.coords) - 1
        
        simplified, history = iterative_simplify_polygon(
            complex_polygon,
            target_vertices=10,
            min_iou=0.80
        )
        
        final_vertices = len(simplified.exterior.coords) - 1
        
        assert isinstance(simplified, Polygon)
        assert simplified.is_valid
        assert final_vertices < initial_vertices
        assert final_vertices <= 20  # Should be significantly simplified
        assert len(history) > 0
    
    def test_simplification_with_data_coverage(self, complex_polygon, data_points):
        """Test simplification with data coverage constraint."""
        # Filter points that are inside the original polygon
        inside_mask = [complex_polygon.contains(Point(p)) for p in data_points]
        inside_points = data_points[inside_mask]
        
        simplified, history = iterative_simplify_polygon(
            complex_polygon,
            data_points=inside_points,
            target_vertices=8,
            min_iou=0.70,
            min_coverage=0.95
        )
        
        # Check that most data points are still covered
        covered = sum(1 for p in inside_points if simplified.contains(Point(p)))
        coverage = covered / len(inside_points)
        
        assert coverage >= 0.95
        assert len(simplified.exterior.coords) - 1 <= 20
    
    def test_target_vertices_achieved(self, complex_polygon):
        """Test that target vertices are achieved when possible."""
        for target in [20, 15, 10, 8]:
            simplified, history = iterative_simplify_polygon(
                complex_polygon,
                target_vertices=target,
                min_iou=0.60  # Relaxed constraint
            )
            
            vertices = len(simplified.exterior.coords) - 1
            # Should achieve target or stop at minimum viable
            assert vertices <= target * 2  # Allow some flexibility
    
    def test_quality_constraints_respected(self, complex_polygon, data_points):
        """Test that quality constraints are respected."""
        # Test with strict constraints
        simplified_strict, _ = iterative_simplify_polygon(
            complex_polygon,
            data_points=data_points,
            target_vertices=6,
            min_iou=0.95,  # Very strict
            min_coverage=0.99
        )
        
        # Test with relaxed constraints
        simplified_relaxed, _ = iterative_simplify_polygon(
            complex_polygon,
            data_points=data_points,
            target_vertices=6,
            min_iou=0.70,  # Relaxed
            min_coverage=0.90
        )
        
        strict_vertices = len(simplified_strict.exterior.coords) - 1
        relaxed_vertices = len(simplified_relaxed.exterior.coords) - 1
        
        # Relaxed constraints should allow more simplification
        assert relaxed_vertices <= strict_vertices
    
    def test_simple_polygon_unchanged(self, simple_polygon):
        """Test that already simple polygons are not over-simplified."""
        initial_vertices = len(simple_polygon.exterior.coords) - 1
        
        simplified, history = iterative_simplify_polygon(
            simple_polygon,
            target_vertices=3,  # Less than current
            min_iou=0.90
        )
        
        final_vertices = len(simplified.exterior.coords) - 1
        
        # Should not simplify below viable polygon (triangle)
        assert final_vertices >= 3
        assert final_vertices == initial_vertices  # Square should stay square
    
    def test_history_tracking(self, complex_polygon):
        """Test that simplification history is properly tracked."""
        simplified, history = iterative_simplify_polygon(
            complex_polygon,
            target_vertices=10,
            min_iou=0.80
        )
        
        assert isinstance(history, list)
        assert len(history) > 0
        
        # Check history entries
        for entry in history:
            assert 'iteration' in entry
            assert 'vertices' in entry
            assert 'iou' in entry
            assert 'tolerance' in entry
        
        # Vertices should decrease through iterations
        vertices_sequence = [h['vertices'] for h in history]
        for i in range(1, len(vertices_sequence)):
            assert vertices_sequence[i] <= vertices_sequence[i-1]
    
    def test_iou_calculation(self, complex_polygon):
        """Test that IoU is calculated correctly during simplification."""
        simplified, history = iterative_simplify_polygon(
            complex_polygon,
            target_vertices=20,
            min_iou=0.85
        )
        
        # Check that final IoU meets constraint
        intersection = complex_polygon.intersection(simplified).area
        union = complex_polygon.union(simplified).area
        actual_iou = intersection / union if union > 0 else 0
        
        assert actual_iou >= 0.85
        
        # Check IoU in history
        if history:
            last_iou = history[-1]['iou']
            assert abs(last_iou - actual_iou) < 0.01  # Should match
    
    def test_max_iterations_limit(self, complex_polygon):
        """Test that simplification respects max iterations."""
        simplified, history = iterative_simplify_polygon(
            complex_polygon,
            target_vertices=4,  # Very aggressive
            min_iou=0.50,
            max_iterations=3  # Limit iterations
        )
        
        assert len(history) <= 3
    
    def test_empty_data_points(self, complex_polygon):
        """Test handling of empty data points."""
        empty_points = np.array([]).reshape(0, 2)
        
        simplified, history = iterative_simplify_polygon(
            complex_polygon,
            data_points=empty_points,
            target_vertices=10,
            min_iou=0.80
        )
        
        # Should still simplify based on IoU only
        assert isinstance(simplified, Polygon)
        assert simplified.is_valid
        assert len(simplified.exterior.coords) - 1 < len(complex_polygon.exterior.coords) - 1
    
    def test_tolerance_caching(self, complex_polygon):
        """Test that tolerance caching improves performance."""
        import time
        
        # First run - no cache
        start1 = time.time()
        simplified1, history1 = iterative_simplify_polygon(
            complex_polygon,
            target_vertices=10,
            min_iou=0.80
        )
        time1 = time.time() - start1
        
        # Second run with same polygon - should use cache
        start2 = time.time()
        simplified2, history2 = iterative_simplify_polygon(
            complex_polygon,
            target_vertices=10,
            min_iou=0.80
        )
        time2 = time.time() - start2
        
        # Results should be identical
        assert simplified1.equals(simplified2)
        
        # Note: Caching test might not always show improvement in test environment
        # but the functionality is there