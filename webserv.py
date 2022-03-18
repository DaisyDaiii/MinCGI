import sys
import socket
import os
import gzip

def connect(config_file): #connect web server
	webserver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	webserver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
	webserver.bind(('', int(config_file['port'])))
	webserver.listen(5)
	while True:
		conn, address = webserver.accept()
		pid = os.fork()
		if pid == 0:
			msg = conn.recv(1024).decode()
			scr = msg.split(' ')[1]
			temp = scr.split("/")
			environment_variable(msg, config_file)
			if(len(temp) == 2):
				get_handler(conn, scr, config_file)
			else:
				cgi_handler(conn, config_file)
			conn.close()
		else:
			conn.close()


def compress(data): # gzip response for extension
	t = gzip.compress(data)
	return t


def get_handler(conn, scr, config_file): # handle static files
	if scr == '/':
		scr = '/index.html'
	path = config_file['staticfiles'] + scr
	content_type = type(scr)
	content = ''
	try:
		f = open(path, 'rb')
		content = f.read()
		f.close()
		header = 'HTTP/1.1 200 OK\n'
	except FileNotFoundError:
		header = 'HTTP/1.1 404 File not found\n'
		list = file_error_html()
		for i in list:
			content += i
		content = content.encode()
	conn.send(header.encode())
	conn.send(content_type.encode())
	conn.send("\n".encode())
	if 'HTTP_ACCEPT_ENCODING' in os.environ.keys() and "gzip" in os.environ['HTTP_ACCEPT_ENCODING']:
		content = compress(content)
	conn.send(content)
	conn.close()

def type(scr): # check file type for static files
	scr = scr.split(".")[1]
	type = ""
	if scr == "html":
		type = 'Content-Type: text/html\n'
	elif scr == "txt":
		type = 'Content-Type: text/plain\n'
	elif scr == "js":
		type = 'Content-Type: application/javascript\n'
	elif scr == "css":
		type = 'Content-Type: text/css\n'
	elif scr == "png":
		type = 'Content-Type: image/png\n'
	elif scr == "jpg" or scr == "jpeg":
		type = 'Content-Type: image/jpeg\n'
	elif scr == "xml":
		type = 'Content-Type: text/xml\n'
	return type

def file_error_html(): # error response content for static files
	list = []
	list.append('<html>\n')
	list.append('<head>\n')
	list.append('	<title>404 Not Found</title>\n')
	list.append('</head>\n')
	list.append('<body bgcolor="white">\n')
	list.append('<center>\n')
	list.append('	<h1>404 Not Found</h1>\n')
	list.append('</center>\n')
	list.append('</body>\n')
	list.append('</html>\n')
	return list

def cgi_handler(conn, config_file): # cgi
	http_variables = {'REQUEST_METHOD': 'Request-Method', 'REQUEST_URI': 'Request-URI', 'QUERY_STRING': 'Query-String', 'REMOTE_ADDRESS': 'Remote-Address', 'REMOTE_PORT': 'Remote-Port', 'SERVER_ADDR': 'Server-Addr', 'SERVER_PORT': 'Server-Port', 'HTTP_USER_AGENT': 'User-Agent', 'HTTP_ACCEPT': 'Accept', 'HTTP_ACCEPT_ENCODING': 'Accept-Encoding', 'HTTP_HOST': 'Host', 'CONTENT_TYPE': 'Content-Type', 'CONTENT_LENGTH': 'Content-Length'}
	status_code = "HTTP/1.1 200 OK\n"
	r, w = os.pipe()
	pid = os.fork()
	if pid == 0:
		try:
			os.close(r)
			w = os.fdopen(w, 'w')
			os.dup2(w.fileno(), 1)
			try:
				os.execl(config_file['exec'], config_file['exec'].split("/")[-1], "." + os.environ['REQUEST_URI'])
			except OSError:
				sys.exit(1)
			except IOError:
				sys.exit(1)
			w.close()
			sys.exit(0)
		except OSError:
			sys.exit(1)
		except Exception:
			sys.exit(1)
	else:
		exit_code = os.wait()
		if exit_code[1]>>8 == 1:
			status_code = 'HTTP/1.1 500 Internal Server Error\n'
		content = ''
		os.close(w)
		r = os.fdopen(r)
		for i in r.readlines():
			flag = False
			if "Status-Code" in i:
				status_code = 'HTTP/1.1 ' + i.split(": ")[1]
				continue
			for j in http_variables:
				if http_variables[j] in i:
					os.environ[j] = i.split(" ")[1].strip("\n")
					flag = True
					break
			if flag == False and i.strip() != "":
				content += i
		content = content.encode()
		header = ''
		for i in http_variables:
			if i in os.environ.keys() and os.environ[i] != " ":
				s = http_variables[i]+": "+os.environ[i]+"\n"
				header += s
		conn.send(status_code.encode())
		conn.send(header.encode())
		conn.send('\n'.encode())
		if 'HTTP_ACCEPT_ENCODING' in os.environ.keys() and "gzip" in os.environ['HTTP_ACCEPT_ENCODING']:
			content = compress(content)
		conn.send(content)
		conn.close()

def environment_variable(msg, config_file): # set environment variables
	requests = msg.split("\r\n")
	os.environ['REQUEST_METHOD'] = requests[0].split(" ")[0]
	url = requests[0].split(" ")[1]
	os.environ['REQUEST_URI'] = url
	if len(url.split("?")) > 1:
		os.environ['QUERY_STRING'] = url.split("?")[1]
		os.environ['REQUEST_URI'] = url.split("?")[0]
	os.environ['REMOTE_ADDRESS'] = requests[1].split(" ")[1].split(":")[0]
	os.environ['REMOTE_PORT'] = requests[1].split(" ")[1].split(":")[1]
	os.environ['SERVER_ADDR'] = socket.gethostbyname(socket.gethostname())
	os.environ['SERVER_PORT'] = config_file['port']
	for i in requests:
		head = i.split(":")[0]
		if 'User_Agent' == head:
			os.environ['HTTP_USER_AGENT'] = i.split(" ")[1]
		elif 'Accept' == head:
			os.environ['HTTP_ACCEPT'] = i.split(" ")[1]
		elif 'Accept_Encoding' == head:
			os.environ['HTTP_ACCEPT_ENCODING'] = i.split(" ")[1]
		elif 'Host' == head:
			os.environ['HTTP_HOST'] = i.split(" ")[1]
		if requests[0].split(" ")[0] == "POST":
			if 'Content-Type' == head:
				os.environ['CONTENT_TYPE'] = i.split(" ")[1]
			elif 'Content-Length' == head:
				os.environ['CONTENT_LENGTH'] = i.split(" ")[1]

def config(argv): # check config file
	config_file = {}
	if len(sys.argv) != 2:
		print("Missing Configuration Argument")
		sys.exit(1)
	try:
		with open(os.path.expanduser(sys.argv[1])) as f:
			line = f.readline()
			while line != "":
				l = line.split("=")
				config_file[l[0]] = l[1].strip("\n")
				line = f.readline()
	except FileNotFoundError:
		print("Unable To Load Configuration File")
		sys.exit(1)
	field = ['staticfiles', 'cgibin', 'port', 'exec']
	for i in field:
		if i not in config_file:
			print("Missing Field From Configuration File")
			sys.exit(1)
	return config_file


if __name__ == '__main__':
	config_file = config(sys.argv)
	connect(config_file)
