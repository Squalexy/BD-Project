import psycopg2
from flask import Flask, jsonify, request, make_response

from functions import *
import logging
import time
import jwt
import datetime

app = Flask(__name__)


##########################################################
# 1 - REGISTER USER
##########################################################

@app.route("/dbproj/user", methods=['POST'])
def register_user():
	content = request.form

	statement = """
				insert into utilizador(username, email, password, admin, banido) 
				values (%s, %s, %s, %s, %s)
				returning id
				"""

	values = (content["username"], content["email"], content["password"], False, False)

	try:
		cursor.execute(statement, values)
		connection.commit()
		rows = cursor.fetchall()
		return jsonify({"userId": str(rows[0][0])})

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return jsonify({'erro': str(error)})


##########################################################
# 2 - LOGIN USER
##########################################################

@app.route('/dbproj/user', methods=['PUT'])
def login_user():
	user = request.form.get('username')
	password = request.form.get('password')

	statement = 'update utilizador set token = md5(random()::text) where username = %s and password = %s returning token;'

	try:
		cursor.execute(statement, (user, password,))
		connection.commit()
		rows = cursor.fetchone()
		if len(rows) == 1:
			return {'token': rows[0]}
		else:
			connection.rollback()
			return is_error("access denied")

	except (Exception, psycopg2.DatabaseError) as AuthError:
		connection.rollback()
		return is_error(str(AuthError))


##########################################################
# 4_A - LISTAGEM WITHOUT TOKEN
##########################################################
"""@app.route('/dbproj/leiloes', methods=['GET'])
def list_auctions():

	listagem = []
	statement = 'select * from leilao where estado = true and now() < datafimleilao'

	try:
		cursor.execute(statement)
		connection.commit()
		rows = cursor.fetchall()
		for row in rows:
			listagem += [{'leilaoId': row[0], 'descricao': row[2]}]
		print(listagem)
		return jsonify(listagem)

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))"""


##########################################################
# 4_B - LISTAGEM WITH TOKEN
##########################################################
@app.route('/dbproj/leiloes', methods=['GET'])
def list_auctions():
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")

	listagem = []
	statement = 'select * from leilao where estado = true and now() < datafimleilao'

	try:
		cursor.execute(statement)
		connection.commit()
		rows = cursor.fetchall()
		for row in rows:
			listagem += [{'leilaoId': row[0], 'descricao': row[2]}]
		return jsonify(listagem)

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))


##########################################################
# MAIN PROGRAM
##########################################################

if __name__ == "__main__":
	connection = db_connection()
	cursor = connection.cursor()
	app.run(debug=True, threaded=True)
