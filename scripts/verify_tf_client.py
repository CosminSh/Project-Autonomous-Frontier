import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'agent_toolkit'))
from bot_client import TFClient

import requests
import json

BASE_URL = os.getenv("TF_BASE_URL", "http://localhost:8000")

def test_client_mappings():
    # 1. Guest login to get an API key
    resp = requests.post(f"{BASE_URL}/auth/guest")
    api_key = resp.json()["api_key"]
    print(f"Testing with API Key: {api_key}")
    
    client = TFClient(api_key, BASE_URL)
    
    print("\n--- Testing TFClient Methods ---")
    
    try:
        agent = client.get_my_agent()
        print(f"[OK] get_my_agent: {agent['name']}")
        
        market = client.get_market_orders()
        print(f"[OK] get_market_orders: {len(market)} orders")
        
        contracts = client.get_available_contracts()
        print(f"[OK] get_available_contracts: {len(contracts)} available")
        
        my_contracts = client.get_my_contracts()
        print(f"[OK] get_my_contracts: {len(my_contracts.get('issued', []))} issued, {len(my_contracts.get('claimed', []))} claimed")
        
        # Test Social
        chat = client.send_chat("Uplink Test Live")
        print(f"[OK] send_chat: {chat['status']}")
        
        history = client.get_chat()
        print(f"[OK] get_chat: {len(history)} messages")
        
        # Test Wiki
        manual = client.get_wiki_manual()
        print(f"[OK] get_wiki_manual: {len(manual)} sections")
        
        print("\n--- TFClient Mapping Verification Complete ---")
        
    except Exception as e:
        print(f"[FAIL] Client Test Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_client_mappings()
