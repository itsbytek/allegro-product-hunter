from app.services.secrets import SecretStore


def test_secure_store_round_trip():
    store = SecretStore(service_name="Allegro Product Hunter Test")
    encrypted = store.encrypt("roundtrip", "local-test-secret")
    assert encrypted != "local-test-secret"
    assert store.decrypt("roundtrip", encrypted) == "local-test-secret"
