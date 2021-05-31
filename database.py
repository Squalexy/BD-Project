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

	# insere os valores do utilizador e regista-se
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

	# request do Postman
	user = request.form.get('username')
	password = request.form.get('password')

	statement = 'update utilizador set token = md5(random()::text) ' \
	            'where username = %s and password = %s ' \
	            'returning token;'

	# obtém o estado "banido" do utilizador
	get_user_state = 'select banido from utilizador where username = %s'

	try:
		cursor.execute(get_user_state, (user,))
		connection.commit()
		state = cursor.fetchone()

	except (Exception, psycopg2.DatabaseError) as AuthError:
		connection.rollback()
		return is_error(str(AuthError))

	try:
		if state[0] is not True:  # se o utilizador não estiver banido
			cursor.execute(statement, (user, password,))
			connection.commit()
			rows = cursor.fetchone()
			if len(rows) == 1:
				return {'token': rows[0]}  # retorna o token do utilizador
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

	# request do Postman
	content = request.form
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")

	# vai buscar o último ID para adicionar um novo ID único
	get_id_statement = "select max(id) from leilao"
	cursor.execute(get_id_statement)
	last_id = cursor.fetchone()
	if last_id is None:  # se ainda não tiverem sido inseridos leilões, cria um novo com id = 1
		last_id = (0,)

	# cria um novo leilão
	statement = "insert into leilao (id, titulo, descricao, precoatual, datafimleilao, estado, codigo, " \
	            "utilizador_username) values (%s, %s, %s, %s, %s, %s, %s, %s)" \
	            "returning id"

	values = (last_id[0] + 1, content["titulo"], content["descricao"], content["precoatual"],
	          content["datafimleilao"], True, content["codigo"], r[0])

	try:
		cursor.execute(statement, values)
		rows = cursor.fetchall()
		connection.commit()
		return jsonify({"leilaoId": str(rows[0][0])})

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return jsonify({'erro': str(error)})


##########################################################
# 4 - LISTAGEM
##########################################################

@app.route('/dbproj/leiloes', methods=['GET'])
def list_auctions():

	# uma vez que, num contexto real, qualquer tipo de utilizador (registado e não registado) pode listar leilões,
	# não é necessário fazer request do token ao Postman

	listagem = []
	statement = 'select * from leilao where estado = true'

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

	# request do Postman
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")

	try:
		listagem = []
		keyword = request.args.get('keyword')
		# keyword pode ser 'descricao' ou 'codigo EAN'
		list_keywords = "select * from leilao where estado = true and now() < datafimleilao and codigo = %s or descricao = %s"
		cursor.execute(list_keywords, (keyword, keyword,))
		rows = cursor.fetchall()
		for row in rows:
			listagem += [{'leilaoId': row[0], 'descricao': row[2]}]
		connection.commit()
		return jsonify(listagem)

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))


##########################################################
# 6 - CONSULTAR DETALHES DE UM LEILÃO
##########################################################

@app.route('/dbproj/leilao/{leilaoId}', methods=['GET'])
def auction_details():

	# request do Postman
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")

	leilaoId = request.args.get('leilaoId')

	# pesquisa pelo leilão
	statement_leilao = "SELECT leilao.id, leilao.descricao, datafimleilao " \
	                   "FROM leilao WHERE leilao.id = %s;"

	# pesquisa pelas mensagens do leilão
	statement_mensagem = "SELECT mensagem.username, conteudo, dataleitura " \
	                     "FROM mensagem WHERE mensagem.leilao_id = %s" \
	                     "ORDER BY dataleitura;"

	# pesquisa pelas licitações do leilão
	statement_licitacao = "SELECT valor, datalicitacao, licitador " \
	                      "FROM licitacao WHERE licitacao.leilao_id = %s" \
	                      "ORDER BY datalicitacao;"

	try:
		cursor.execute(statement_leilao, leilaoId)
		leilao = cursor.fetchone()

		cursor.execute(statement_mensagem, leilaoId)
		mensagens = cursor.fetchall()
		lista_mensagens = []
		for mensagem in mensagens:
			lista_mensagens += [(mensagem[0], mensagem[1], mensagem[2])]

		cursor.execute(statement_licitacao, leilaoId)
		licitacoes = cursor.fetchall()
		lista_licitacoes = []
		for licitacao in licitacoes:
			lista_licitacoes += [(licitacao[2], licitacao[0], licitacao[1])]

		listagem = {"leilaoId": leilao[0], "descricao": leilao[1], "datafimleilao": leilao[2],
		            "mensagens": lista_mensagens, "licitacoes": lista_licitacoes}

		connection.commit()
		return listagem

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))


##########################################################
# 7 - LISTAR TODOS OS LEILOES EM QUE O UTILIZADOR TENHA ATIVIDADE
##########################################################

@app.route('/dbproj/leiloes7', methods=['GET'])
def listagem_leiloes_ligados_ao_user():

	# request do Postman
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")

	try:
		listagem = []  # lista onde vão estar todos os leilões

		# procura os leilões onde o utilizador seja criador
		cursor.execute("select * from leilao where utilizador_username = %s", [r[0]])
		rows = cursor.fetchall()
		for row in rows:
			# titulo, descricao, precoatual, datafim, codigo, utilizador_username
			listagem += [
				{'titulo': row[1], 'descricao': row[2], 'precoatual': row[3], 'datafim': row[4], 'codigo': row[6],
				 'Criador leilao': row[7]}]

		# procura os leilões onde utilizador seja licitador
		cursor.execute("select * from licitacao where licitador = %s", [r[0]])

		rows = cursor.fetchall()
		for row in rows:
			# vai buscar as informacoes de cada leilao
			# titulo, descricao, precoatual, datafim, codigo, utilizador_username
			row_aux = funcao_aux(row[2])
			listagem += [{'titulo': row_aux[0][1], 'descricao': row_aux[0][2], 'precoatual': row_aux[0][3],
			              'datafim': row_aux[0][4], 'codigo_aux': row_aux[0][6], 'Criador leilao': row_aux[0][7]}]

		connection.commit()
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

	# request do Postman
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

		# procura o valor atual do leilão onde pretende fazer a licitação
		cursor.execute("select precoatual from leilao where id = %s", [leilaoId])
		preco_atual = cursor.fetchone()

		# verifica que a licitação é maior que o valor máximo atual
		if float(preco_atual[0]) > float(licitacao):
			connection.rollback()
			return is_error("Licitação é menor que o preço atual")

		# tentou fazer-se da seguinte forma mas o python estava a dar erro:
		# "WHERE %s > (SELECT precoatual FROM leilao where id = %s)", logo a seguir aos VALUES

		# faz uma licitação
		licitacao_statement = "INSERT INTO licitacao (valor,datalicitacao,leilao_id,utilizador_username,licitador) " \
		                      "VALUES (%s,%s,%s,%s,%s)"

		licitacao_values = (licitacao, dt_string, leilaoId, rows[7], r[0])

		cursor.execute(licitacao_statement, licitacao_values)

		# trigger acontece aqui

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

	# request do Postman
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")

	leilao_id = request.args.get('leilaoId')
	titulo = request.form.get('titulo')
	descricao = request.form.get('descricao')

	try:

		# vai buscar o leilao a ser alterado e vamos colocar as informacoes textuais na tabela de historico
		statement = 'select * from leilao where id = %s and utilizador_username = %s'
		cursor.execute(statement, (leilao_id, r[0],))
		connection.commit()
		rows = cursor.fetchall()

		if not rows:  # se o leilão não existir
			return is_error("Sem leiloes")

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))

	# insere as alterações no histórico textual
	statement = "insert into historico_textual (titulo, descricao, leilao_id, data_modif) values (%s, %s, %s, %s)"

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
		if titulo is None and descricao is None: # se não houver nenhuma alteração textual
			return is_error("Sem alteracoes a efetuar")
		elif titulo is None: # se apenas se alterar o título
			cursor.execute("update leilao set descricao = %s where id = %s", (descricao, leilao_id,))
		elif descricao is None: # se apenas se alterar a descrição
			cursor.execute("update leilao set titulo = %s where id = %s", (titulo, leilao_id,))
		else: # se se alterar título e descrição
			cursor.execute("update leilao set titulo = %s, descricao = %s where id = %s",
			               (titulo, descricao, leilao_id,))
		connection.commit()

		# vai buscar as informacoes do leilao (atualizadas) e imprime
		cursor.execute("select * from leilao where id = %s", [leilao_id])
		rows = cursor.fetchall()
		listagem = [{'titulo': rows[0][1], 'descricao': rows[0][2], 'precoatual': rows[0][3], 'datafim': rows[0][4],
		             'codigo_aux': rows[0][6], 'Criador leilao': rows[0][7]}]

		connection.commit()
		return jsonify(listagem)

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))


##########################################################
# 10 - ESCREVER MENSAGEM NO MURAL DE UM LEILÃO
##########################################################

@app.route('/dbproj/{idLeilao}/mural', methods=['POST'])
def write_message():

	# request do Postman
	token = request.args.get('token')
	cursor.execute("select username from utilizador where token = %s and banido = false", [token])
	r = cursor.fetchone()
	if r is None:
		return is_error("Access denied!")

	idLeilao = request.args.get('idLeilao')
	mensagem = request.args.get('mensagem')

	now = datetime.now()

	try:

		# insere a mensagem no mural do leilão
		statement = "insert into mensagem(leilao_id, username, conteudo, tipo, data_envio) values (%s, %s, %s, %s, %s)"
		values = (idLeilao, r[0], mensagem, "mural", now.strftime("%Y-%m-%d %H:%M:%S"))
		cursor.execute(statement, values)

		# armazena as mensagens do mural do leilão
		mensagens = "select data_envio, username, conteudo from mensagem where leilao_id = %s and tipo = %s;"
		msg_values = (idLeilao, "mural")
		cursor.execute(mensagens, msg_values)
		fetch_msg = cursor.fetchall()

		# procura o nome do criador do leilão
		seleciona_criador = "select utilizador_username from leilao where id = %s"
		cursor.execute(seleciona_criador, (idLeilao,))
		criador = cursor.fetchone()

		# notifica o criador do leilão
		notifica_criador = "insert into mensagem (leilao_id, username, conteudo, tipo, data_envio) values (%s, %s, %s, %s, %s)"
		values_criador = (
			idLeilao, criador[0], "Nova mensagem publicada no mural", "notificacao", now.strftime("%Y-%m-%d %H:%M:%S"))
		cursor.execute(notifica_criador, values_criador)

		# procura os utilizadores que escreveram no mural a notificar da nova mensagem do mural
		users_a_notificar = "select DISTINCT username from mensagem where tipo = %s and leilao_id = %s and username != %s"
		cursor.execute(users_a_notificar, ("mural", idLeilao, r[0],))
		users = cursor.fetchall()

		# notifica esses utilizadores
		statement_two = "insert into mensagem (leilao_id, username, conteudo, tipo, data_envio) values (%s, %s, %s, %s, %s)"
		for user in users:
			print(user)
			now = datetime.now()
			values_users = (
			idLeilao, user[0], "Nova mensagem publicada no mural", "notificacao", now.strftime("%Y-%m-%d %H:%M:%S"))
			cursor.execute(statement_two, values_users)

		connection.commit()
		return jsonify(fetch_msg)

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return jsonify({'erro': str(error)})


##########################################################
# 13 - TÉRMINO DO LEILÃO
##########################################################

@app.route('/dbproj/terminar', methods=['POST'])
def end_auctions():

	# request do Postman
	token = request.args.get('token')
	cursor.execute("select * from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None or r[3] is False:
		return is_error("Access denied!")

	try:

		# update do estado do leilão, mete-o inativo e mete a descrição = "Leilão terminou"
		now = datetime.now()
		expirated_auctions = "UPDATE leilao " \
		                     "SET estado = %s, descricao = %s " \
		                     "WHERE %s > datafimleilao and estado = true"
		expired_values = ("false", "Leilão terminou!", now.strftime("%Y-%m-%d %H:%M:%S"))
		cursor.execute(expirated_auctions, expired_values)

		# acede aos leilões já terminados
		cursor.execute("SELECT * FROM leilao WHERE estado = false AND descricao LIKE 'Leilão terminou!'")
		leiloesterminados = cursor.fetchall()

		# percorre cada leilão terminado para saber na tabela licitação qual o maior valor e de quem é
		for leilaoterminado in leiloesterminados:
			print(leilaoterminado)
			cursor.execute("select licitador "
			               "from licitacao "
			               "where valor = %s", [leilaoterminado[3]])
			valor = cursor.fetchone()

			# depois de encontrado o maior valor adiciona na tabela utilizador e diz que o leilão foi ganho
			for v in valor:
				print(v)
				cursor.execute("update utilizador set leiloes_ganhos = leiloes_ganhos + 1 where username = %s", [v])
				cursor.execute("update leilao set descricao = 'Leilão ganho!' where id = %s", [leilaoterminado[0]])
				break

		cursor.execute("SELECT * FROM leilao WHERE estado = false")
		rows = cursor.fetchall()

		connection.commit()

		return jsonify(rows)

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return jsonify({'erro': str(error)})


##########################################################
# 14 - ADMINISTRADOR PODE CANCELAR O LEILAO
##########################################################

@app.route('/dbproj/cancelar/{leilaoId}', methods=['POST'])
def cancelar_leilao():

	# request do Postman
	token = request.args.get('token')
	cursor.execute("select * from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None or r[3] is False:
		return is_error("Access denied!")

	try:
		leilaoId = request.args.get('leilaoId')
		now = datetime.now()  # datetime object containing current date and time
		dt_string = now.strftime("%Y-%m-%d %H:%M:%S")  # dd/mm/YY H:M:S

		# verifica que o leilão ainda é válido, caso contrário já terminou
		cursor.execute("select * from leilao where estado = true and now() < datafimleilao and id = %s", [leilaoId])

		# atualiza datafimleilao para a data de agora e atualiza estado para false
		cursor.execute("update leilao set datafimleilao = %s, estado = %s "
		               "where id = %s", (dt_string, leilaoId, leilaoId,))

		# atualiza licitações do utilizador, metendo-as como canceladas
		cursor.execute("update licitacao set cancelada = true where leilao_id = %s", [leilaoId])

		# vai buscar as informacoes do leilao (atualizadas) e imprime
		cursor.execute("select * from leilao where id = %s", [leilaoId])
		rows = cursor.fetchall()
		listagem = [{'titulo': rows[0][1], 'descricao': rows[0][2], 'precoatual': rows[0][3], 'datafim': rows[0][4],
		             'estado': rows[0][5], 'codigo': rows[0][6], 'Criador leilao': rows[0][7]}]

		# vai à tabela de licitações, procura as pessoas que fizeram licitacoes no leilão cancelado
		notificar_pessoas = "select * from licitacao where leilao_id = %s"
		cursor.execute(notificar_pessoas, leilaoId)
		notificar_pessoas = cursor.fetchall()

		for notifica_pessoa in notificar_pessoas:
			# envia notificação às pessoas que licitaram no leilao a dizer que este foi cancelado
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

	# request do Postman
	token = request.args.get('token')
	cursor.execute("select * from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None or r[3] is False:
		return is_error("Access denied!")

	user_banido = request.form.get('username')

	try:
		# vai banir o utilizador
		cursor.execute("update utilizador set banido = true where username = %s", [user_banido])

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))

	try:
		# vai buscar os leiloes que ele criou e coloca o estado deles a false
		cursor.execute("update leilao set estado = false where utilizador_username = %s", [user_banido])

		# vai buscar os leiloes que ele criou, ja atualizados
		cursor.execute("select * from leilao where utilizador_username = %s", [user_banido])
		rows = cursor.fetchall()

		for row in rows:
			# para cada leilao, coloca todas as licitacoes desse leilao como canceladas
			cursor.execute("update licitacao set cancelada = true where leilao_id = %s", [row[0]])

			# vai à tabela de licitações, procura as pessoas que fizeram licitacoes num determinado leilao
			notificar_pessoas = "select * from licitacao where leilao_id = %s and licitador != %s"
			cursor.execute(notificar_pessoas, (row[0], user_banido,))
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

		# vai retornar ids de leilões distintos em que o user licitou
		statement = 'select DISTINCT leilao_id from licitacao where licitador = %s'
		cursor.execute(statement, (user_banido,))
		rows = cursor.fetchall()

		for row in rows:

			# vai buscar a cada leilao cada licitação do user banido
			aux = 'select MAX(valor) from licitacao where licitador = %s and leilao_id = %s'
			cursor.execute(aux, (user_banido, row[0],))
			maximo = cursor.fetchone()

			# vai atualizar no leilao o valor atual
			aux_dois = 'update leilao set precoatual = %s where id = %s'
			cursor.execute(aux_dois, (maximo[0], row[0],))

			# vai cancelar todas as licitacoes desse leilao cujo valor seja maior que o maximo
			aux_tres = 'update licitacao set cancelada = true where leilao_id = %s and valor > %s'
			cursor.execute(aux_tres, (row[0], maximo[0],))

			# vai buscar a licitacao mais alta para depois se atualizar o valor
			aux_quatro = 'select MAX(valor) from licitacao where leilao_id = %s'
			cursor.execute(aux_quatro, (row[0],))
			auxiliar = cursor.fetchone()

			# vai atualizar a licitação mais alta para o valor maximo
			aux_cinco = 'update licitacao set valor = %s, cancelada = false where leilao_id = %s and valor = %s and licitador != %s'
			cursor.execute(aux_cinco, (maximo[0], row[0], auxiliar[0], user_banido,))

			# vai à tabela de licitações, procura as pessoas que fizeram licitacoes num determinado leilao
			notificar_pessoas = "select * from licitacao where leilao_id = %s and licitador != %s"
			cursor.execute(notificar_pessoas, (row[0], user_banido,))
			notificar_pessoas = cursor.fetchall()

			for notifica_pessoa in notificar_pessoas:

				# envia notificação às pessoas que licitaram no leilao
				notificacao_statement = "insert into mensagem (username, conteudo, tipo, data_envio, leilao_id)" \
				                        "values (%s, %s, %s, %s, %s)"
				notif = "Algumas licitacoes do leilãoId [{}] foram canceladas, verifique as suas licitacoes!".format(
					row[0])
				notificacao_values = (notifica_pessoa[4], notif, "notificacao", datetime.now(), row[0])
				cursor.execute(notificacao_statement, notificacao_values)

		connection.commit()
		return jsonify('Sucesso')

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))


##########################################################
# 16 - ADMINISTRADOR PODE OBTER ESTATISTICAS
##########################################################

@app.route('/dbproj/estatisticas', methods=['GET'])
def estatisticas_leilao():

	# request do Postman
	token = request.args.get('token')
	cursor.execute("select * from utilizador where token = %s", [token])
	r = cursor.fetchone()
	if r is None or r[3] is False:
		return is_error("Access denied!")

	try:

		# top 10 utilizadores com mais leiloes criados
		cursor.execute("select utilizador_username,count(utilizador_username) "
		               "from leilao group by utilizador_username order by count(utilizador_username) desc limit 10")
		top10utilizadores = cursor.fetchall()

		# top 10 utilizadores que mais leiloes venceram
		cursor.execute("select username,leiloes_ganhos from utilizador  "
		               "group by username order by leiloes_ganhos desc limit 10")
		top10utilizadoresvencedores = cursor.fetchall()

		# numero total de leiloes nos ultimos 10 dias
		cursor.execute("select * from leilao where datafimleilao < current_date  - interval '10' day "
		               "and estado = false OR datafimleilao > current_date and estado = true")
		leiloes10dias = cursor.fetchall()

		connection.commit()

		return jsonify("Top 10 utilizadores com mais leiloes criados ", top10utilizadores,
		               "Top 10 utilizadors que mais leiloes venceram ",
		               top10utilizadoresvencedores, "Numero total de leiloes nos ultimos 10 dias ",
		               len(leiloes10dias))

	except (Exception, psycopg2.DatabaseError) as error:
		connection.rollback()
		return is_error(str(error))


##########################################################
# MAIN PROGRAM
##########################################################

if __name__ == "__main__":
	app.run(debug=True, threaded=True)
