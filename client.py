# The following code can be run using Python3 
from socket import *
import sys
import threading
import time
import signal

client_port_number = {}

# Function to receive tcp messages from the server 
# and print them to the client's terminal
# This is the function started by receive_tcp_thread
def receive_tcp_messages(client_tcp_socket, client_username, server_host):
    while True:
        try:
            data = client_tcp_socket.recv(1024)
            received_message = data.decode()

            # We add the udp port number to the client_port_number dictionary whenever a client calls /p2pvideo
            if received_message.split(" ")[0] == 'p2pvideo' and len(received_message.split(" ")) == 3:
                client_port_number[received_message.split(" ")[1]] = received_message.split(" ")[2]
            else:
                print(" ".join(received_message.split()[1:]))
                # Prompt needs to be added because the normal functionality doesnt allow for the prompt to be printed when messages are received
                if received_message.split(" ")[0] == 'msg_recieve' or received_message.split(" ")[0] == 'groupmsg_recieve':
                    print("\nEnter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /p2pvideo, /logout):")      
        except:
            break

# Function to receive udp messages from other clients
# and print them to the client's terminal
# This is the function started by receive_udp_thread
def receive_udp_messages(client_udp_socket, client_username, server_host):
    while True:
        try:
            data, sender_address = client_udp_socket.recvfrom(1024)
            received_message = data.decode()

            if received_message.split(" ")[0] == '/logout':
                break

            chunks = received_message.split()
            audience_username = chunks[1]
            original_filename = chunks[2]

            server_filename = f"{audience_username}_{original_filename}"
            # From the internet
            with open(server_filename, 'ab') as file:  
                   while True:
                    data, address = client_udp_socket.recvfrom(1024)
                    if data == b"EOF":  
                        break
                    file.write(data)

            print(f"File ({original_filename}) received from {audience_username}\n")

            # Prompt needs to be added because the normal functionality doesnt allow for the prompt to be printed when a file is received
            print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /p2pvideo, /logout):") 
        except:
            break

# Function to login the client and handle blocking, locking, and multiple login failures
def login(client_tcp_socket, client_udp_socket, client_udp_port, server_host):
    print("Please login \n")
    input_username = input("Username: ")
    input_password = input("Password: ")

    if len(input_username.strip().split(" ")) != 1:
        print("Error: Invalid username or password. Please try again.\n")
        main()

    message = f"credentials {input_username.strip()} {input_password.strip()} {client_udp_port}"
    client_tcp_socket.send(message.encode())

    data = client_tcp_socket.recv(1024)
    received_message = data.decode()

    if received_message == "login success":
        print("Welcome to TESSENGER!")
        client_tcp_socket.send(f"Log {input_username} {client_udp_port}".encode())
        handle_client(client_tcp_socket, client_udp_socket, input_username, server_host, client_udp_port)
    elif received_message == "login failed":
        print("Login failed. Please try again.\n")
        login(client_tcp_socket, client_udp_socket, client_udp_port, server_host)
    elif received_message == "account locked":
        print("Your account has been locked. Please try again later.")
    elif received_message == "client blocked":
        print("Your account is blocked due to multiple login failures. Please try again later")

def msgto(client_tcp_socket, command, sender_username):
    if len(command.split(" ")) < 3:
        print("Error: Invalid syntax. Command should be in the form of /msgto USERNAME MESSAGE_CONTENT\n")
        return
    receiver_username = command.split(" ")[1]
    message = " ".join(command.split()[2:])
    message = f"/msgto {sender_username} {receiver_username} {message}"
    client_tcp_socket.send(message.encode())

def activeuser(client_tcp_socket):
    message = "/activeuser"
    client_tcp_socket.send(message.encode())

def creategroup(client_tcp_socket, command, client_username):
    if len(command.split(" ")) < 3:
        print("Error: Invalid syntax. Command should be in the form of /creategroup GROUPNAME USERNAMES\n")
        return
    members = command.split(" ")[2:]
    message = f"/creategroup {command.split()[1]} {client_username} {' '.join(members)}"
    client_tcp_socket.send(message.encode())

def joingroup(client_tcp_socket, command, client_username):
    if len(command.split(" ")) != 2:
        print("Error: Invalid syntax. Command should be in the form of /joingroup GROUPNAME\n")
        return
    message = f"/joingroup {command.split()[1]} {client_username}"
    client_tcp_socket.send(message.encode())

def groupmsg(client_tcp_socket, command, client_username):
    if len(command.split(" ")) < 3:
        print("Error: Invalid syntax. Command should be in the form of /groupmsg GROUPNAME MESSAGE_CONTENT\n")
        return
    message = f"/groupmsg {command.split()[1]} {client_username} {' '.join(command.split()[2:])}"
    client_tcp_socket.send(message.encode())

def p2pvideo(client_udp_socket, client_tcp_socket, command, presenter_username, server_host):
    if len(command.split(" ")) != 3:
        print("Error: Invalid syntax. Command should be in the form of /p2pvideo USERNAME FILENAME\n")
        return
    message = command.strip() + " " + presenter_username
    client_tcp_socket.send(message.encode())
    time.sleep(0.0001)
    filename = command.split(" ")[2]
    audience_username = command.split(" ")[1]
    
    if audience_username not in client_port_number:
        return

    server_address = (server_host, int(client_port_number[audience_username]))
    # From the internet
    with open(filename, 'rb') as file:
        message = message 
        client_udp_socket.sendto(message.encode(), server_address)
        data = file.read(1024)
        while data:
            client_udp_socket.sendto(data, server_address)
            data = file.read(1024)
            time.sleep(0.00001)
        end_marker = b"EOF"  
        client_udp_socket.sendto(end_marker, server_address)

    print("File sent successfully")

def logout(client_tcp_socket, client_udp_socket, client_username, client_udp_port, server_host):
    message = f"/logout {client_username}"
    client_tcp_socket.send(message.encode())
    client_udp_socket.sendto(message.encode(), (server_host, client_udp_port))
    client_udp_socket.close()
    client_tcp_socket.close()  
    sys.exit()  

def user_input(client_tcp_socket, client_udp_socket, client_username, server_host, client_udp_port):
    commands = ["/msgto", "/activeuser", "/creategroup", "/joingroup", "/groupmsg", "/p2pvideo", "/logout"]
    while True:
        print("\n Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /p2pvideo, /logout):")
        command = input().strip()

        if command.split(" ")[0] not in commands:
            print("Error: Invalid command. Please try again.\n")
        elif command.split(" ")[0] == "/msgto":
            msgto(client_tcp_socket, command, client_username)
        elif command.strip() == "/activeuser":
            activeuser(client_tcp_socket)
        elif command.split(" ")[0] == "/creategroup":
            creategroup(client_tcp_socket, command, client_username)
        elif command.split(" ")[0] == "/joingroup":
            joingroup(client_tcp_socket, command, client_username)
        elif command.split(" ")[0] == "/groupmsg":
            groupmsg(client_tcp_socket, command, client_username)
        elif command.split(" ")[0] == "/p2pvideo":
            p2pvideo(client_udp_socket, client_tcp_socket, command, client_username, server_host)
        elif command.strip() == "/logout":
            logout(client_tcp_socket, client_udp_socket, client_username, client_udp_port, server_host)

        time.sleep(0.0001)

# All threads are started here
def handle_client(client_tcp_socket, client_udp_socket, client_username, server_host, client_udp_port):
    receive_tcp_thread = threading.Thread(target=receive_tcp_messages, args=(client_tcp_socket, client_username, server_host))
    receive_tcp_thread.start()
    receive_udp_thread = threading.Thread(target=receive_udp_messages, args=(client_udp_socket, client_username, server_host))
    receive_udp_thread.start()
    user_input_thread = threading.Thread(target=user_input, args=(client_tcp_socket, client_udp_socket, client_username, server_host, client_udp_port))
    user_input_thread.start()

    receive_tcp_thread.join()
    receive_udp_thread.join()
    user_input_thread.join()

def main():
    if len(sys.argv) != 4:
        print("\nError: Usage, python3 client.py SERVER_IP SERVER_PORT CLIENT_UDP_PORT\n")
        exit(0)
    server_host = sys.argv[1]
    server_port = int(sys.argv[2])
    server_address = (server_host, server_port)

    client_udp_port = int(sys.argv[3])
    client_tcp_socket = socket(AF_INET, SOCK_STREAM)
    client_tcp_socket.connect(server_address)
    client_udp_socket = socket(AF_INET, SOCK_DGRAM)
    client_udp_socket.bind((server_host, client_udp_port))

    login(client_tcp_socket, client_udp_socket, client_udp_port, server_host)

    client_tcp_socket.close()
    client_udp_socket.close()


if __name__ == "__main__":
    main()
