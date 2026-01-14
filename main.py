from csv_print import csv_print_data, csv_print_header
from runfile import read_csv
import sys

def main():
    default_filename: str = "JFN-Groudtruth-Simulator_result.csv"
    filename: str = csv_print_header(default_filename)
    vehicles:list = read_csv(sys.argv[1])  # Get filename from system arguments
    # vehicles:list = read_csv("simulation_data.csv")  # Get filename from default arguments


    all_done=False
    while not all_done:
        """
        iterate through a list of vehicle objects and call their update methods
        """
        for v in vehicles:
            v.update(1, 10000, 10000)
        csv_print_data(vehicles, filename)

        all_done = all(v.action == 'done' for v in vehicles)




if __name__== "__main__":
    main()