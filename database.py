from flask import Flask, jsonify, request
from functions import *
from datetime import datetime

app = Flask(__name__)
connection = db_connection()
cursor = connection.cursor()


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

	statement = 'update utilizador set token = md5(random()::text) ' \
	            'where username = %s and password = %s ' \
	            'returning token;'

	get_user_state = 'select banido from utilizador where username = %s'

	try:
		cursor.execute(get_user_state, (user,))
		connection.commit()
		state = cursor.fetchone()

	except (Exception, psycopg2.DatabaseError) as AuthError:
		connection.rollback()
		return is_error(str(AuthError))

	try:
		if state[0] is not True:
			cursor.execute(statement, (user, password,))
			connection.commit()
			rows = cursor.fetchone()
			if len(rows) == 1:
				return {'token': rows[0]}
			else:
				connection.rollback()
				return is_error("access denied")
		else:
			connection.rollback()
			return is_error("access denied, user banned")

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
		rows = cursor.fetchone()

		# verifica que a licitação é maior que o valor máximo atual
		cursor.execute("select * from licitacao where  valor < %s", [licitacao])
		valid_value = cursor.fetchone()

		# faz uma licitação
		licitacao_statement = "insert into licitacao (valor,datalicitacao,leilao_id,utilizador_username,licitador) " \
		                      "values (%s, %s,%s,%s,%s);"
		licitacao_values = (licitacao, dt_string, leilaoId, rows[7], r[0])
		cursor.execute(licitacao_statement, licitacao_values)

		# trigger aqui

		connection.commit()

		return jsonify('Sucesso')

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))


##########################################################
# 9 - EDITAR PROPRIEDADES DE UM LEILAO - DIOGO
##########################################################

@app.route('/dbproj/leilao/{leilaoId}', methods=['PUT'])
def editar_propriedades_leilao():
	# token
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")
	# fim token

	leilao_id = request.args.get('leilaoId')
	titulo = request.form.get('titulo')
	descricao = request.form.get('descricao')

	try:
		# vai buscar o leilao a ser alterado e vamos colocar as informacoes textuais na tabela de historico
		statement = 'select * from leilao where id = %s and utilizador_username = %s'
		cursor.execute(statement, (leilao_id, r[0],))
		connection.commit()
		rows = cursor.fetchall()
		if rows == []:
			return is_error("Sem leiloes")
	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))
	statement = """
                        insert into historico_textual (titulo, descricao, leilao_id, data_modif) 
                        values (%s, %s, %s, %s)
                        """
	try:
		now = datetime.now()  # datetime object containing current date and time
		dt_string = now.strftime("%Y-%m-%d %H:%M:%S")
		values = (rows[0][1], rows[0][2], rows[0][0], dt_string)
		cursor.execute(statement, values)
		connection.commit()
	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))

	# vai atualizar o leilao
	try:
		if titulo is None and descricao is None:
			return is_error("Sem alteracoes a efetuar")
		elif titulo is None:
			cursor.execute("update leilao set descricao = %s where id = %s", (descricao, leilao_id,))
		elif descricao is None:
			cursor.execute("update leilao set titulo = %s where id = %s", (titulo, leilao_id,))
		else:
			cursor.execute("update leilao set titulo = %s, descricao = %s where id = %s",
			               (titulo, descricao, leilao_id,))
		connection.commit()

		# vai buscar as informacoes do leilao (atualizadas) e imprime
		cursor.execute("select * from leilao where id = %s", [leilao_id])
		connection.commit()
		rows = cursor.fetchall()
		listagem = [{'titulo': rows[0][1], 'descricao': rows[0][2], 'precoatual': rows[0][3], 'datafim': rows[0][4],
		             'codigo_aux': rows[0][6], 'Criador leilao': rows[0][7]}]
		return jsonify(listagem)

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
# 13 - TÉRMINO DO LEILÃO
##########################################################

@app.route('/dbproj/terminar', methods=['POST'])
def end_auctions():
	token = request.args.get('token')
	cursor.execute("select * from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None or r[3] is False:
		return is_error("Access denied!")

	try:
		now = datetime.now()
		expirated_auctions = "UPDATE leilao " \
		                     "SET estado = %s, descricao = %s" \
		                     "WHERE %s > datafimleilao"
		expired_values = ("false", "Leilão terminou!", now.strftime("%Y-%m-%d %H:%M:%S"))
		cursor.execute(expirated_auctions, expired_values)
		connection.commit()

		cursor.execute("SELECT * FROM leilao WHERE estado = false")
		connection.commit()
		rows = cursor.fetchall()

		return jsonify(rows)

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return jsonify({'erro': str(error)})


##########################################################
# 14 - ADMINISTRADOR PODE CANCELAR O LEILAO
##########################################################

@app.route('/dbproj/cancelar/{leilaoId}', methods=['POST'])
def cancelar_leilao():
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")

	try:
		leilaoId = request.args.get('leilaoId')
		now = datetime.now()  # datetime object containing current date and time
		dt_string = now.strftime("%Y-%m-%d %H:%M:%S")  # dd/mm/YY H:M:S

		# verifica que o leilão é válido,se ja nao acabou basicamente
		cursor.execute("select * from leilao where estado = true and now() < datafimleilao and id = %s", [leilaoId])
		connection.commit()

		# atualiza datafimleilao para a data de agora
		cursor.execute("update leilao set datafimleilao = %s where id = %s", (dt_string, leilaoId,))

		# atualiza estado de leilao para false
		cursor.execute("update leilao set estado = %s where id = %s", ("false", leilaoId))
		connection.commit()

		# atualiza licitacoes
		cursor.execute("update licitacao set cancelada = true where leilao_id = %s", [leilaoId])
		connection.commit()

		# vai buscar as informacoes do leilao (atualizadas) e imprime
		cursor.execute("select * from leilao where id = %s", [leilaoId])

		connection.commit()
		rows = cursor.fetchall()
		listagem = [{'titulo': rows[0][1], 'descricao': rows[0][2], 'precoatual': rows[0][3], 'datafim': rows[0][4],
		             'estado': rows[0][5], 'codigo': rows[0][6], 'Criador leilao': rows[0][7]}]

		# vai à tabela de licitações, procura as pessoas que fizeram licitacoes num determinado leilao
		notificar_pessoas = "select * from licitacao where leilao_id = %s"
		cursor.execute(notificar_pessoas, leilaoId)
		connection.commit()
		notificar_pessoas = cursor.fetchall()
		for notifica_pessoa in notificar_pessoas:
			# envia notificação às pessoas que licitaram no leilao
			notificacao_statement = "insert into mensagem (username, conteudo, tipo, data_envio, leilao_id)" \
			                        "values (%s, %s, %s, %s, %s)"
			notif = "O leilãoId [{}] foi cancelado!".format(leilaoId)
			notificacao_values = (notifica_pessoa[4], notif, "notificacao", now, leilaoId)
			cursor.execute(notificacao_statement, notificacao_values)
		connection.commit()
		return jsonify(listagem)

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))


############################################################
# 15 - UM ADMIN PODE BANIR PERMANENTEMENTE UM USER
############################################################

@app.route('/dbproj/banir', methods=['PUT'])
def banir_user():
	# token
	token = request.args.get('token')
	statement = 'select username from utilizador where token = %s and admin = true'
	cursor.execute(statement, (token,))
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")
	# fim token

	user_banido = request.form.get('username')
	# vai banir o utilizador
	try:
		cursor.execute("update utilizador set banido = true where username = %s", [user_banido])
	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))

	try:
		# vai buscar os leiloes que ele criou e coloca o estado deles a false
		cursor.execute("update leilao set estado = false where utilizador_username = %s", [user_banido])
		connection.commit()

		# vai buscar os leiloes que ele criou ja atualizados
		cursor.execute("select * from leilao where utilizador_username = %s", [user_banido])
		connection.commit()
		rows = cursor.fetchall()

		for row in rows:
			# para cada leilao, coloca todas as licitacoes desse leilao como canceladas
			cursor.execute("update licitacao set cancelada = true where leilao_id = %s", [row[0]])
			connection.commit()
			# vai à tabela de licitações, procura as pessoas que fizeram licitacoes num determinado leilao
			notificar_pessoas = ("select * from licitacao where leilao_id = %s and licitador != %s")
			cursor.execute(notificar_pessoas, (row[0], user_banido,))
			connection.commit()
			notificar_pessoas = cursor.fetchall()
			for notifica_pessoa in notificar_pessoas:
				# envia notificação às pessoas que licitaram no leilao
				notificacao_statement = "insert into mensagem (username, conteudo, tipo, data_envio, leilao_id)" \
				                        "values (%s, %s, %s, %s, %s)"
				notif = "O leilãoId [{}] foi cancelado!".format(row[0])
				notificacao_values = (notifica_pessoa[4], notif, "notificacao", datetime.now(), row[0])
				cursor.execute(notificacao_statement, notificacao_values)

		# vai as licitacoes que ele efetuou e coloca-as como canceladas
		statement = 'update licitacao set cancelada = true where licitador = %s'
		cursor.execute(statement, (user_banido,))
		connection.commit()

		# vai retornar eleicoes distintas em que o user licitou
		statement = 'select DISTINCT leilao_id from licitacao where licitador = %s'
		cursor.execute(statement, (user_banido,))
		connection.commit()
		rows = cursor.fetchall()
		for row in rows:
			# vai buscar a cada leilao o valor maximo que o user banido apostou
			aux = 'select MAX(valor) from licitacao where licitador = %s and leilao_id = %s'
			cursor.execute(aux, (user_banido, row[0],))
			connection.commit()
			maximo = cursor.fetchone()

			# vai atualizar no leilao o valor atual
			aux_dois = 'update leilao set precoatual = %s where id = %s'
			cursor.execute(aux_dois, (maximo[0], row[0],))
			connection.commit()

			# vai cancelar todas as licitacoes desse leilao cujo valor seja maior que o maximo
			aux_tres = 'update licitacao set cancelada = true where leilao_id = %s and valor > %s'
			cursor.execute(aux_tres, (row[0], maximo[0],))
			connection.commit()

			# vai buscar a licitacao mais alta para depois se atualizar o valor
			aux_quatro = 'select MAX(valor) from licitacao where leilao_id = %s'
			cursor.execute(aux_quatro, (row[0],))
			auxiliar = cursor.fetchone()
			connection.commit()

			# vai atualizar a proposta maior para o valor maximo
			aux_cinco = 'update licitacao set valor = %s, cancelada = false where leilao_id = %s and valor = %s and licitador != %s'
			cursor.execute(aux_cinco, (maximo[0], row[0], auxiliar[0], user_banido,))
			connection.commit()
			# vai à tabela de licitações, procura as pessoas que fizeram licitacoes num determinado leilao
			notificar_pessoas = ("select * from licitacao where leilao_id = %s and licitador != %s")
			cursor.execute(notificar_pessoas, (row[0], user_banido,))
			connection.commit()
			notificar_pessoas = cursor.fetchall()
			for notifica_pessoa in notificar_pessoas:
				# envia notificação às pessoas que licitaram no leilao
				notificacao_statement = "insert into mensagem (username, conteudo, tipo, data_envio, leilao_id)" \
				                        "values (%s, %s, %s, %s, %s)"
				notif = "Algumas licitacoes do leilãoId [{}] foram canceladas, verifique as suas licitacoes!".format(
					row[0])
				notificacao_values = (notifica_pessoa[4], notif, "notificacao", datetime.now(), row[0])
				cursor.execute(notificacao_statement, notificacao_values)
		return jsonify('Sucesso')

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))


##########################################################
# MAIN PROGRAM
##########################################################

if __name__ == "__main__":
	app.run(debug=True, threaded=True)
