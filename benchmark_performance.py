#!/usr/bin/env python3
"""
Performance benchmark script to test sequential vs concurrent API calls in NFL Query Service.
"""

import asyncio
import time
from App.services.Nfl_query_service import NFLQueryService
from App.services.concurrent_nfl_query_service import ConcurrentNFLQueryService

async def benchmark_query_service():
    """
    Benchmark both sequential and concurrent implementations
    """
    # Test queries that require multiple API calls
    test_queries = [
        "Who are the top quarterbacks this season?",  # player_rankings - multiple APIs
        "What's the injury status for the Chiefs this week?",  # injuries - multiple APIs
        "Show me the schedule for the Packers",  # schedule - multiple APIs
        "What are the current standings?",  # standings - multiple APIs
        "Get me the weather forecasts for this week",  # weather - multiple APIs
    ]
    
    # Initialize services
    sequential_service = NFLQueryService()
    concurrent_service = ConcurrentNFLQueryService()
    
    print("🏈 NFL Query Service Performance Benchmark")
    print("=" * 50)
    
    for query in test_queries:
        print(f"\n📊 Testing query: '{query}'")
        print("-" * 40)
        
        # Test sequential implementation
        start_time = time.time()
        try:
            sequential_result = await sequential_service.process_query(query)
            sequential_time = time.time() - start_time
            sequential_endpoints = len(sequential_result.get("data_sources", []))
            print(f"⏱️  Sequential time: {sequential_time:.2f} seconds")
            print(f"📡 Sequential endpoints called: {sequential_endpoints}")
        except Exception as e:
            sequential_time = time.time() - start_time
            print(f"❌ Sequential failed: {e}")
            print(f"⏱️  Sequential time (failed): {sequential_time:.2f} seconds")
            continue
        
        # Test concurrent implementation
        start_time = time.time()
        try:
            concurrent_result = await concurrent_service.process_query(query)
            concurrent_time = time.time() - start_time
            concurrent_endpoints = len(concurrent_result.get("data_sources", []))
            print(f"⚡ Concurrent time: {concurrent_time:.2f} seconds")
            print(f"📡 Concurrent endpoints called: {concurrent_endpoints}")
        except Exception as e:
            concurrent_time = time.time() - start_time
            print(f"❌ Concurrent failed: {e}")
            print(f"⚡ Concurrent time (failed): {concurrent_time:.2f} seconds")
            continue
        
        # Calculate improvement
        if sequential_time > 0 and concurrent_time > 0:
            improvement = ((sequential_time - concurrent_time) / sequential_time) * 100
            speedup = sequential_time / concurrent_time
            print(f"🚀 Performance improvement: {improvement:.1f}%")
            print(f"🏃 Speedup factor: {speedup:.2f}x")
        
        print("-" * 40)
    
    print(f"\n✅ Benchmark completed!")

async def simple_benchmark():
    """
    Simple benchmark for a single query type that uses multiple API calls
    """
    print("🔬 Simple Benchmark: Player Rankings Query")
    print("=" * 50)
    
    query = "Who are the top PPR quarterbacks this season?"
    
    # Initialize services
    sequential_service = NFLQueryService()
    concurrent_service = ConcurrentNFLQueryService()
    
    # Warm up
    print("🔥 Warming up services...")
    try:
        await sequential_service.process_query("Who are the Chiefs?")
        await concurrent_service.process_query("Who are the Chiefs?")
    except:
        pass
    
    # Run multiple iterations for more accurate measurement
    iterations = 3
    sequential_times = []
    concurrent_times = []
    
    print(f"\n📈 Running {iterations} iterations...")
    
    for i in range(iterations):
        print(f"\n--- Iteration {i + 1} ---")
        
        # Sequential test
        start_time = time.time()
        try:
            await sequential_service.process_query(query)
            sequential_time = time.time() - start_time
            sequential_times.append(sequential_time)
            print(f"Sequential: {sequential_time:.3f}s")
        except Exception as e:
            print(f"Sequential failed: {e}")
            continue
        
        # Concurrent test
        start_time = time.time()
        try:
            await concurrent_service.process_query(query)
            concurrent_time = time.time() - start_time
            concurrent_times.append(concurrent_time)
            print(f"Concurrent: {concurrent_time:.3f}s")
        except Exception as e:
            print(f"Concurrent failed: {e}")
            continue
    
    # Calculate averages
    if sequential_times and concurrent_times:
        avg_sequential = sum(sequential_times) / len(sequential_times)
        avg_concurrent = sum(concurrent_times) / len(concurrent_times)
        
        print(f"\n📊 Results Summary:")
        print(f"Sequential average: {avg_sequential:.3f}s")
        print(f"Concurrent average: {avg_concurrent:.3f}s")
        
        if avg_concurrent > 0:
            improvement = ((avg_sequential - avg_concurrent) / avg_sequential) * 100
            speedup = avg_sequential / avg_concurrent
            print(f"🚀 Average improvement: {improvement:.1f}%")
            print(f"🏃 Average speedup: {speedup:.2f}x")

if __name__ == "__main__":
    print("Starting NFL Query Service Performance Benchmark...")
    
    # You can choose which benchmark to run
    # asyncio.run(benchmark_query_service())  # Full benchmark
    asyncio.run(simple_benchmark())  # Simple benchmark
