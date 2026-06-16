# Dark Vessel information

This is an experimental module which will likely be expanded if we get another year of funding.

# src programs:
## Simulator

This module contains a simulator. This heuristically models the approximate nature of vessels doing specific activities to create an AIS track.
It can also produce data that is difficult to analyze, such as tracks that intersect or tracks that are very close together.

## Classifiers
The sequence classifier is a transformer model which trains off of regular AIS data to predict the current activithy of the ship. 
The classifier.py file uses features computed in the features folder to learn what each vessel is most likely doing and what its risk is.
The partial track classifier is essentially the same thing as the sequence classifier, however, trains differently and is better for sparse track data rather than full long track data. 
There is a geoclassifier which classifies based off of region.

## Anomaly Detection
This uses classical approaches to ship data analysis instead of using Artificial Intelligence to classify if vessels are acting wierd. 
Some of these methods are finding temporal gaps, finding duplicate mmsis, and other traditional methods of finding suspicious anomalies.

## Feature identification:
This computes different features from the AIS ship data for a machine learning mdel to learn. 
It computes things like zig zag index to find how zig zaggy it is, circular index to see how circular its path is, ect.

## Real Data:
This folder has functions to convert AIS data of different formats to the csv AIS data that this program uses. There are also programs for analysis of the data and data for specific fishing areas. 
This program may need to be deleted or significantly modified to match the AIS data that we have in our database. 

## Utils:
This contains things such as which defintions on which device should be used (CPU v GPU)
Constant variable deinitions such as what regions there.
Constant variables for visualization

## Reingorcement learning:
This folder creates and trains a DQN or Dual Q Network which is a network which has the feature inputs. It starts with one nerual netowrk that splits into two. The output of the firt represents how interesting or anomalous the vessel is while the other is for classifying the vessel's activity. 

# main programs:

## dark_vessel_analysis:
This program trains a reinforcement learning (RL) model and uses it to analyze maritime data to detect and evaluate “dark vessel” activity across different ocean regions. It can run analysis for a specific region or all regions, with optional visualization of both the model behavior and results.

## generate_dataset_figures:
This script generates visualization figures for a synthetic maritime tracking dataset, producing one detailed plot per scenario type plus an overview panel of all scenarios. Each figure overlays multiple geographic variants in a normalized nautical-mile frame and highlights vessel behavior, activity labels, and tracking challenges such as dark gaps and identity confusion.

## generate_figures:
Creates figures such as images for presentaton/demonstration of how well the code worked.

## Encoder_decoder_test:
This is a test/proof of concept. It takes all of the various AIS points and it learns their patterns with a GRU. The GRU then incodes the track in fewer neurons to get the "gist" of the tracks and then everything gets decoded from those few neurons. You can train this network with normal AIS data, and then, if evaluated, the model should output a large value if there is an anomaly in that ship's AIS path.

## The main program
This project implements a maritime Activity Intelligence Engine that analyzes vessel movement data (simulated and real AIS) to classify ship behavior, detect anomalies, and identify suspicious activity such as dark vessels, AIS gaps, and potential ship-to-ship transfers. It uses machine learning models to infer vessel activity (e.g., fishing, transit, loitering) and computes risk scores for illegal, unreported, or evasive behavior.

The system supports both synthetic simulation for model training and evaluation across multiple regions, as well as real-world AIS ingestion from external databases or files. It also includes advanced analytics such as geo-enrichment, behavioral baselining, rendezvous detection, and dark-period trajectory reconstruction. Results are stored in a PostgreSQL database and can be exported as reports and visualizations for further intelligence analysis.

