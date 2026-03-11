from print import csv_print_data, csv_print_header, json_print_data, json_print_header
from runfile import read_json
import sys

def main():
    try:
        vehicles, settings = read_json(sys.argv[1])  # Get runfile name from system arguments
    except IndexError:
        print("No runfile specified, using default 'example_ground_truth_runfile.json'")
        vehicles, settings = read_json("example_ground_truth_runfile.json")  # Get filename from default arguments

    if settings.print_format == "csv":
        print("Using CSV print format")
        filename2D, filename3D = csv_print_header(settings)
    elif settings.print_format == "json":
        print("Using JSON print format")
        filename2D, filename3D = json_print_header(settings)
    print(f"{filename2D}, {filename3D}")
    all_done=False
    while not all_done:
        """
        iterate through a list of vehicle objects and call their update methods
        """
        for v in vehicles:
            v.update(settings, vehicles)
        if settings.print_format == "csv":
            csv_print_data(vehicles, filename2D, filename3D, settings)
        elif settings.print_format == "json":
            json_print_data(vehicles, filename2D, filename3D, settings)
        all_done = all(v.done == True for v in vehicles)
        settings.advance_time(settings.time_step)
    
    settings.ocean_current.close()


if __name__== "__main__":
    main()