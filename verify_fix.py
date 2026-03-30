import sys
sys.path.append('c:/Users/usuario/Videos/dasboard')
import sentiment

# Test 1: Empty headlines
print("Testing empty headlines...")
res = sentiment.aggregate_sentiment([])
print(f"Result keys: {res.keys()}")
assert 'details' in res
print(f"Details: {res['details']}")

# Test 2: Simulating error (no model)
print("\nTesting no model simulation...")
# We can't easily mock HAS_TRANSFORMERS here without reloading, 
# but we can check if it currently handles errors.
res = sentiment.aggregate_sentiment(["Test headline"])
print(f"Result keys: {res.keys()}")
assert 'details' in res
print(f"Details: {res['details']}")

print("\nVerification complete!")
