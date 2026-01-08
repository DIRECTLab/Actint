from csv_print import csv_print_data, csv_print_header

def main():
    filename: str = csv_print_header()

    all_done=False
    while not all_done:
        """
        iterate through a linked list of vehicle objects and call their update methods
        """
        csv_print_data([], filename)
        pass # Replace with actual simulation loop logic




if __name__== "__main__":
    main()