import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import ssl
import certifi

async def test_conn():
    uri = "mongodb+srv://mistrytejasm_db_user:5CapDEaRj7A364Cx@cluster0.it3qbcx.mongodb.net/?appName=Cluster0"
    
    print("Testing default connection with timeout...")
    try:
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=2000)
        print(await client.list_database_names())
    except Exception as e:
        print("Default failed:", e)

    print("\nTesting connection with certifi and timeout...")
    try:
        client = AsyncIOMotorClient(uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=2000)
        print(await client.list_database_names())
    except Exception as e:
        print("Certifi failed:", e)

    print("\nTesting connection with tlsAllowInvalidCertificates=True and timeout...")
    try:
        client = AsyncIOMotorClient(uri, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=2000)
        print(await client.list_database_names())
    except Exception as e:
        print("tlsAllowInvalidCertificates failed:", e)

asyncio.run(test_conn())
