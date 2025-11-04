import csv

def check_transit_station(station_names):
    total_transit_stations = 0
    for station_name, line_names in station_names.items():
        if len(line_names) > 1:
            print(f"Station {station_name}, line_count: {len(line_names)}" )
            total_transit_stations += 1
    print(f"Total transit stations: {total_transit_stations}")

def main():
    station_names = {}
    with open('data/line_stops.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            station_name = row['stop_name']
            line_name = row['line_name']

            if station_name not in station_names:
                station_names[station_name] = {line_name}
            else:
                if line_name not in station_names[station_name]:
                    station_names[station_name].add(line_name)
                else:
                    print(f"Station {station_name}, line_name: {line_name} already exists")
    
    check_transit_station(station_names)

if __name__ == "__main__":
    main()

            
            
    