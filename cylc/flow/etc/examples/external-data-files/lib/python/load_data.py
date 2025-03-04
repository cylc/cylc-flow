import csv
import json


def load_csv(filename):
    with open(filename, 'r') as csv_file:
        return list(csv.DictReader(csv_file))


def load_json(filename):
    with open(filename, 'r') as json_file:
        return json.load(json_file)
