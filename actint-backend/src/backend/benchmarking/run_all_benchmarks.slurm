#!/bin/bash

#SBATCH --job-name=run-actint-benchmarks
#SBATCH --nodes=1
#SBATCH --nodelist=terry
#SBATCH --ntasks=1
#SBATCH --exclusive
#SBATCH --gpus=1
#SBATCH --mem=50G
#SBATCH --output=./slurm_logs/%x-%j.log
#SBATCH --error=./slurm_logs/%x-%j.log

source /home/software/miniforge3/etc/profile.d/conda.sh
conda activate actint

# Run the Dreamer Anymal C play script
python ./benchmark_agents.py --run-all-benchmarks
