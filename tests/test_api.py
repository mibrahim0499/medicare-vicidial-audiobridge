"""Tests for API endpoints"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_detailed_health_check():
    """Test detailed health check endpoint"""
    response = client.get("/api/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "asterisk_configured" in data
    assert "database_configured" in data


def test_get_calls():
    """Test get calls endpoint"""
    response = client.get("/api/calls")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_calls_with_limit():
    """Test get calls with limit"""
    response = client.get("/api/calls?limit=10")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_call_not_found():
    """Test get non-existent call"""
    response = client.get("/api/calls/nonexistent")
    assert response.status_code == 404

