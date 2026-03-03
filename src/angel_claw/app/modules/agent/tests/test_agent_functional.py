def test_index(client):
    response = client.get('/agent/')
    assert response.status_code == 200
