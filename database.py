import psycopg2
from flask import Flask, jsonify, request, make_response

from functions import *
import logging
import time
import jwt
from datetime import datetime

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
# 3 - CRIAR NOVO LEILAO
##########################################################

@app.route('/dbproj/leilao', methods=['POST'])
def cria_leilao():
	content = request.form
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")

	# vai buscar o último ID para adicionar um novo ID único
	get_id_statement = "select max(id) from leilao"
	cursor.execute(get_id_statement)
	connection.commit()
	last_id = cursor.fetchone()
	if last_id is None:
		last_id = (0,)

	# cria um novo leilão
	statement = "insert into leilao (id, titulo, descricao, precoatual, datafimleilao, estado, codigo, " \
	            "utilizador_username) values (%s, %s, %s, %s, %s, %s, %s, %s)" \
	            "returning id"

	values = (last_id[0] + 1, content["titulo"], content["descricao"], content["precoatual"],
	          content["datafimleilao"], True, content["codigo"], r[0])

	try:
		cursor.execute(statement, values)
		connection.commit()
		rows = cursor.fetchall()
		return jsonify({"leilaoId": str(rows[0][0])})

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return jsonify({'erro': str(error)})


##########################################################
# 4 - LISTAGEM
##########################################################

@app.route('/dbproj/leiloes', methods=['GET'])
def list_auctions():
	# token
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")
	# fim token

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
# 5 - PESQUISAR LEILOES EXISTENTES
##########################################################

@app.route('/dbproj/leiloes/{keyword}', methods=['GET'])
def listagem_leiloes_especificos():
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")

	try:
		listagem = []
		keyword = request.args.get('keyword')
		cursor.execute("select * from leilao where estado = true and now() < datafimleilao and codigo = %s", [keyword])
		connection.commit()
		rows = cursor.fetchall()
		for row in rows:
			listagem += [{'leilaoId': row[0], 'descricao': row[2]}]
		cursor.execute("select * from leilao where estado = true and now() < datafimleilao and descricao = %s",
		               [keyword])
		connection.commit()
		rows = cursor.fetchall()
		for row in rows:
			listagem += [{'leilaoId': row[0], 'descricao': row[2]}]
		return jsonify(listagem)
	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))


##########################################################
# 6 - CONSULTAR DETALHES DE UM LEILÃO
##########################################################

@app.route('/dbproj/leilao/{leilaoId}', methods=['GET'])
def auction_details():
	# token
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")
	# fim token

	n_commits = 0

	leilaoId = request.args.get('leilaoId')

	statement_leilao = "SELECT leilao.id, leilao.descricao, datafimleilao " \
	                   "FROM leilao WHERE leilao.id = %s;"
	statement_mensagem = "SELECT mensagem.username, conteudo, dataleitura " \
	                     "FROM mensagem WHERE mensagem.leilao_id = %s" \
	                     "ORDER BY dataleitura;"
	statement_licitacao = "SELECT valor, datalicitacao, licitador " \
	                      "FROM licitacao WHERE licitacao.leilao_id = %s" \
	                      "ORDER BY datalicitacao;"

	try:
		cursor.execute(statement_leilao, leilaoId)
		connection.commit()
		n_commits += 1
		leilao = cursor.fetchone()

		cursor.execute(statement_mensagem, leilaoId)
		connection.commit()
		n_commits += 1
		mensagens = cursor.fetchall()
		lista_mensagens = []
		for mensagem in mensagens:
			lista_mensagens += [(mensagem[0], mensagem[1], mensagem[2])]

		cursor.execute(statement_licitacao, leilaoId)
		connection.commit()
		n_commits += 1
		licitacoes = cursor.fetchall()
		lista_licitacoes = []
		for licitacao in licitacoes:
			lista_licitacoes += [(licitacao[2], licitacao[0], licitacao[1])]

		listagem = {"leilaoId": leilao[0], "descricao": leilao[1], "datafimleilao": leilao[2],
		            "mensagens": lista_mensagens, "licitacoes": lista_licitacoes}
		return listagem

	except (Exception, psycopg2.DatabaseError) as error:
		for i in range(n_commits):
			connection.rollback()
		return is_error(str(error))


##########################################################
# 7 - LISTAR TODOS OS LEILOES EM QUE O UTILIZADOR TENHA ATIVIDADE
##########################################################

@app.route('/dbproj/leiloes7', methods=['GET'])
def listagem_leiloes_ligados_ao_user():
	# token
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")
	# fim token

	try:
		listagem = []
		cursor.execute("select * from leilao where utilizador_username = %s", [r[0]])
		connection.commit()
		rows = cursor.fetchall()
		for row in rows:
			# titulo, descricao, precoatual, datafim, codigo, utilizador_username
			listagem += [
				{'titulo': row[1], 'descricao': row[2], 'precoatual': row[3], 'datafim': row[4], 'codigo': row[6],
				 'Criador leilao': row[7]}]
		cursor.execute("select * from licitacao where licitador = %s", [r[0]])
		connection.commit()
		rows = cursor.fetchall()
		for row in rows:
			print(row)
			# vai buscar as informacoes de cada leilao
			# titulo, descricao, precoatual, datafim, codigo, utilizador_username
			row_aux = funcao_aux(row[2])
			print("AQUI")
			print(row_aux)
			listagem += [{'titulo': row_aux[0][1], 'descricao': row_aux[0][2], 'precoatual': row_aux[0][3],
			              'datafim': row_aux[0][4], 'codigo_aux': row_aux[0][6], 'Criador leilao': row_aux[0][7]}]
		return jsonify(listagem)
	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))


def funcao_aux(id_leilao):
	cursor.execute("select * from leilao where id = %s", [id_leilao])
	connection.commit()
	row_aux = cursor.fetchall()
	return row_aux


##########################################################
# 8 - EFETUAR UMA LICITACAO NUM LEILAO
##########################################################

@app.route('/dbproj/licitar/{leilaoId}/{licitacao}', methods=['GET'])
def licitar_leilao():
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")

	try:
		leilaoId = request.args.get('leilaoId')
		licitacao = request.args.get('licitacao')

		now = datetime.now()  # datetime object containing current date and time
		dt_string = now.strftime("%Y-%m-%d %H:%M:%S")  # dd/mm/YY H:M:S

		# verifica que o leilão é válido
		cursor.execute("select * from leilao where estado = true and now() < datafimleilao and id = %s", [leilaoId])
		connection.commit()
		rows = cursor.fetchone()

		# verifica que a licitação é maior que o valor máximo atual
		cursor.execute("select * from licitacao where  valor < %s", [licitacao])
		connection.commit()

		# faz uma licitação
		licitacao_statement = "insert into licitacao (valor,datalicitacao,leilao_id,utilizador_username,licitador) " \
		                      "values (%s, %s,%s,%s,%s);"
		licitacao_values = (licitacao, dt_string, leilaoId, rows[7], r[0])
		cursor.execute(licitacao_statement, licitacao_values)
		connection.commit()

		# atualiza o valor na tabela de leilões
		atualizar_valor = "UPDATE leilao SET precoatual = %s WHERE id = %s;"
		atualizar_values = (licitacao, leilaoId)
		cursor.execute(atualizar_valor, atualizar_values)
		connection.commit()

		# vai à tabela de licitações, procura a pessoa que fez a última licitação
		ultima_licitacao = "select licitador from licitacao where valor = " \
		                   "(select max(valor) from licitacao where leilao_id = %s)"
		cursor.execute(ultima_licitacao, leilaoId)
		connection.commit()
		ultimo_licitador = cursor.fetchone()

		# envia notificação à última pessoa que leiloou no artigo
		notificacao_statement = "insert into mensagem (username, conteudo, tipo, data_envio, leilao_id)" \
		                        "values (%s, %s, %s, %s, %s)"
		notif = "Surgiu uma melhor licitação no leilãoId [{}]".format(leilaoId)
		notificacao_values = (ultimo_licitador, notif, "notificacao", now, leilaoId)
		cursor.execute(notificacao_statement, notificacao_values)
		connection.commit()

		return jsonify('Sucesso')

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))


##########################################################
# 10 - ESCREVER MENSAGEM NO MURAL DE UM LEILÃO
##########################################################

@app.route('/dbproj/{idLeilao}/mural', methods=['POST'])
def write_message():
	# token
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")
	# fim token

	idLeilao = request.args.get('idLeilao')
	mensagem = request.args.get('mensagem')

	statement = "insert into mensagem(leilao_id, username, conteudo, tipo, data_envio) values (%s, %s, %s, %s, %s)"

	mensagens = "select data_envio, username, conteudo from mensagem where leilao_id = %s and tipo = %s;"

	now = datetime.now()
	values = (idLeilao, r[0], mensagem, "mural", now.strftime("%Y-%m-%d %H:%M:%S"))
	msg_values = (idLeilao, "mural")

	try:
		cursor.execute(statement, values)
		connection.commit()
		cursor.execute(mensagens, msg_values)
		connection.commit()
		fetch_msg = cursor.fetchall()
		return jsonify(fetch_msg)

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return jsonify({'erro': str(error)})


##########################################################
# 11 - ESCREVER MENSAGEM NO MURAL DE UM LEILÃO
##########################################################


##########################################################
# MAIN PROGRAM
##########################################################

if __name__ == "__main__":
	connection = db_connection()
	cursor = connection.cursor()
	app.run(debug=True, threaded=True)
