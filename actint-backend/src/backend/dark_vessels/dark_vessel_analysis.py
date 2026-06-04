"""
run with python dark_vesel_analysis.py
arguments:
    --build: build the RL model (this will also run the analysis after building)
    --vis: visualise the model on building and the analysis results
    --all: run analysis on all regions instead of just brazil_eez
"""


import time
import argparse
import backend.dark_vessels.main as dark_vessels
import backend.dark_vessels.src.reinforcement_learning.train_rl_agent as train_rl_agent

def build_model():
    print("Building the RL model...")
    start_time = time.time()
    train_rl_agent.main()
    end_time = time.time()
    print(f"Model building time: {end_time - start_time:.2f} seconds")

def run_analysis(region="brazil_eez", visualise=False, all=False):
    print("Running dark vessel analysis...")
    start_time = time.time()
    if all:
        dark_vessels.main(visualise=visualise)
    else:
        dark_vessels.run_region(region, visualise=visualise)
    end_time = time.time()
    print(f"Dark vessel analysis time: {end_time - start_time:.2f} seconds")

# This is mostly for manual testing, both building and analysing the model should be done automatically during general use
if __name__ == "__main__":

    import sys
    print(sys.argv)

    #handle command line arguments
    parser = argparse.ArgumentParser(description="Build and Analyze RL model")
    parser.add_argument("--build", action="store_true", help="Build the RL model")
    parser.add_argument("--vis", action="store_true", help="Visualize the results")
    parser.add_argument("--all", action="store_true", help="Run analysis on all regions")
    args = parser.parse_args()

    if args.build:
        build_model()
    run_analysis(visualise=args.vis, all=args.all)
