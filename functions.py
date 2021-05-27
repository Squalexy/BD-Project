import json
import psycopg2


##########################################################
# DATABASE ACCESS
##########################################################

def load_admin_config():
	with open("config/config.json") as opening:
		return json.load(opening)


def db_connection():
	admin_config = load_admin_config()
	db = psycopg2.connect(user=admin_config["user"],
	                      password=admin_config["password"],
	                      host=admin_config["host"],
	                      port=admin_config["port"],
	                      database=admin_config["database"])
	return db


def is_error(message="unknown error"):
	return {"error": message}