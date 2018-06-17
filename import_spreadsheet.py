#!/usr/bin/env python3

import requests
import csv
import json
import logging
from io import StringIO

source_data = ''
try:
    source = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vQ6CChYk0cXlp_R_L2r9Enkar8qmDdGtu2CCE6dYYdU391PBt6zzePYQAkTJ5zJ6DHvkPsWu3Oty206/pub?gid=447869804&single=true&output=csv'
    data_request = requests.get(source)
    source_data = data_request.content.decode()

    if 'Inténtalo de nuevo' in source_data:
        raise Exception('Too many requests')
except Exception as e:
    logging.exception('Could not obtain data from google')
    exit(1)

api_url = 'http://localhost:3000/api'
headers = {'Content-type': 'application/json', 'Accept': 'application/json', 'Cache-Control': 'no-cache'}

def upsert_collection(data):
    url = api_url + '/collections'
    verify_url = api_url + '/collections?filter={"where":{"legacy_id":"' + data['legacy_id'] + '"}}'

    r = requests.get(verify_url, data=json.dumps(data), headers=headers)
    response = r.json()
    if len(response) > 0:
        collectionID = response[0]['id']
        update_url = api_url + '/collections/{}'.format(collectionID)
        r = requests.put(update_url, data=json.dumps(data), headers=headers)
        logging.debug(r.json())
        if r.status_code != 200:
            return

        return r.json()
    else:
        r = requests.post(url, data=json.dumps(data), headers=headers)
        if r.status_code != 200:
            return

        return r.json()

def upsert_contact(data):
    url = api_url + '/contacts'
    verify_url = api_url + '/contacts?filter={"where":{"legacy_id":"' + data['legacy_id'] + '"}}'

    r = requests.get(verify_url, data=json.dumps(data), headers=headers)
    response = r.json()
    if len(response) > 0:
        contactID = response[0]['id']
        update_url = api_url + '/contacts/{}'.format(contactID)
        r = requests.put(update_url, data=json.dumps(data), headers=headers)
        if r.status_code != 200:
            return

        return r.json()
    else:
        r = requests.post(url, data=json.dumps(data), headers=headers)
        if r.status_code != 200:
            return

        return r.json()


def upsert_products(collectionID, products):
    url = api_url + '/collections/{}/products'.format(collectionID)
    requests.delete(url, headers=headers)

    for product in products:
        data = {"number": product.strip()}
        r = requests.post(url, data=json.dumps(data), headers=headers)
        if r.status_code != 200:
            logging.warning("Unable to register product {} in {}".format(product, collectionID))

f = StringIO(source_data)
reader = csv.DictReader(f)
i = 0
for row in reader:
    i += 1
    logging.info("Processing row {}".format(i))
    try:
        data = {
            'legacy_id': row['id'],
            'number': row['Nombre del centro de acopio'],
            'address': row['Dirección (agregada)'],
        }

        try:
            data['geopos'] = {'lat': float(row['lat']), 'lng': float(row['lon'])}
        except Exception as e:
            logging.warning("ignored geopos lat:{} long:{}".format(row['lat'], row['lon']))


        collection = upsert_collection(data)
        if not collection:
            logging.info('retry lat and long switched')
            try:
                data['geopos'] = {'lat': float(row['lon']), 'lng': float(row['lat'])}
            except Exception as e:
                logging.warning("ignored geopos row: {} lat:{} long:{}".format(row['ID'], row['lon'], row['lat']))

            collection = upsert_collection(data)

        if not collection:
            logging.error('ignored row ID: {}'.format(json.dumps(data)))
            continue

        # POST CONTACT
        contact_data = {
            "legacy_id": "{}-{}".format(data['legacy_id'], 1),
            "collectionID": collection['id'],
            "number": row['Nombre Contacto'],
            "email": row['Correo'],
            "twitter": row['Twitter'],
            "facebook": row['Facebook'],
            "phone": row['Teléfono']
        }

        contact = upsert_contact(contact_data)
        if not contact:
            logging.error("Can't add contact {}".format(json.dumps(contact_data)))


        # POST PRODUCTS
        products_raw = row['Necesidades']
        products_raw = products_raw.replace('y', ',')
        products_raw = products_raw.replace('.', ',')
        products = products_raw.split(",")

        upsert_products(collection['id'], products)

        logging.info("OK")

    except Exception as e:
        logging.exception("ignored row {}".format(row))
