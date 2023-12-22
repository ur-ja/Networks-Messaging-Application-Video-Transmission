# The following code can be run using Python3 
import sys
import socket
import time
from threading import Thread
from datetime import datetime
import os.path
import signal

if len(sys.argv) != 3:
    print("\n===== Error usage, python3 server.py SERVER_PORT MAX_INVALID_ATTEMPTS ======\n")
    exit(0)
    
if not sys.argv[2].isdigit() or not isinstance(int(sys.argv[2]), int):
    print("\n===== Error: Invalid value for MAX_INVALID_ATTEMPTS. Please provide an integer value. ======\n")
    exit(0)

server_host = "127.0.0.1"
server_port = int(sys.argv[1])
server_address = (server_host, server_port)
max_invalid_attempts = sys.argv[2]
max_invalid_attempts = int(max_invalid_attempts)
connected_clients = {} # key: username, value: client socket, timestamp, ip address, udp port
invalid_attempts = {} # Tracks login attempts
blocked_clients = {} # Holds temporarily blocked users
groups = {} # Holds groups and their members
members_joined = {} # Keeps track of members who have joined the group

if max_invalid_attempts < 1 or max_invalid_attempts > 5:
    print("\n===== Error: Invalid number of allowed failed consecutive attempts:", max_invalid_attempts)
    print("The valid value of argument number is an integer between 1 and 5 ======\n")
    exit(0)

server_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_tcp_socket.bind(server_address)

# From the internet handles graaceful server shutdown and removes log files
def shutdown_server(sig, frame):
    print("\n===== Server is shutting down gracefully =====")
    if os.path.isfile('userlog.txt'):
        os.remove('userlog.txt')
    if os.path.isfile('messagelog.txt'):
        os.remove('messagelog.txt')
    for group in groups:
        if os.path.isfile(f'{group}_messagelog.txt'):
            os.remove(f'{group}_messagelog.txt')
    print("===== All log files deleted =====")
    server_tcp_socket.close()  
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown_server)

# Thread handles each TCP client connection 
class ClientThread(Thread):
    def __init__(self, client_address, client_socket):
        Thread.__init__(self)
        self.client_address = client_address
        self.client_socket = client_socket
        self.client_alive = False

        print("===== New connection created for: ", client_address)
        self.client_alive = True
        
    def run(self):
        message = ''
        while self.client_alive:
            data = self.client_socket.recv(1024)
            message = data.decode()
            
            if message == '':
                self.client_alive = False
                print("===== the user disconnected - ", client_address)
                break
            
            if message.split(" ")[0] == 'credentials':
                self.authenticate(message)
            elif message.split(" ")[0] == 'Log':
                self.handle_user_log(message)
            elif message.split(" ")[0] == '/msgto':
                self.handle_msg_to(message)
            elif message.split(" ")[0] == '/activeuser':
                self.handle_active_user()
            elif message.split(" ")[0] == '/creategroup':
                self.handle_create_group(message)
            elif message.split(" ")[0] == '/joingroup':
                self.handle_join_group(message)
            elif message.split(" ")[0] == '/groupmsg':
                self.handle_group_msg(message)
            elif message.split(" ")[0] == '/p2pvideo':
                self.handle_p2p_video(message)
            elif message.split(" ")[0] == '/logout':
                self.handle_logout(message)
    
    # This function sends information to the client who requested a p2p video
    # in order for the client to initiate a udp connection to send a file as they require port numbers
    # as well as error handling
    def handle_p2p_video(self, message):
        print('===== P2P video request received =====')
        audience_username = message.split(" ")[1]
        filename = message.split(" ")[2]
        presenter_username = message.split(" ")[3]
        presenter_udp_port = connected_clients[presenter_username][3]

        if audience_username == presenter_username:
            message = f"p2pvideo Error: User {audience_username} cannot send messages to themselves."
            print(f"===== Error: User {audience_username} cannot send messages to themselves. =====")
            self.client_socket.send(message.encode())
            return
        if audience_username not in connected_clients:
            message = f"p2pvideo Error: User {audience_username} is not logged in."
            print(f"===== Error: User {audience_username} is not logged in. =====")
            self.client_socket.send(message.encode())
            return
        audience_udp_port = connected_clients[audience_username][3]
        message = f"p2pvideo {audience_username} {audience_udp_port}"
        print(f"===== Sending p2pvideo credentials =====")
        self.client_socket.send(message.encode())


    def handle_logout(self, message):
        username = message.split(" ")[1]
        print(f"===== Logout request received from user {username} =====")
        with open("userlog.txt", "r") as infile:
            lines = infile.readlines()
            
        # Edit userlog.txt to remove the user and update the serial numbers
        with open("userlog.txt", "w") as outfile:
            serial_number_offset = 0
            for line in lines:
                parts = line.strip().split('; ')
                if len(parts) >= 3 and parts[2] == username:
                    serial_number_offset = -1
                else:
                    parts[0] = str(int(parts[0]) + serial_number_offset)
                    outfile.write('; '.join(parts) + '\n')
        
        if username in connected_clients:
            del connected_clients[username]

        print(f"===== User {username} logged out. =====")
        message = f"logout Bye, {username}!"
        self.client_socket.send(message.encode())

    def handle_group_msg(self, message):
        group_name = message.split(" ")[1]
        username = message.split(" ")[2]
        message_content = " ".join(message.split(" ")[3:])

        # Error handling
        if group_name not in groups:
            print("===== Error: Group does not exist. =====")
            message = f"groupmsg Error: Group {group_name} does not exist."
            self.client_socket.send(message.encode())
            return

        if username not in groups[group_name]:
            print("===== Error: User is not a member of the group. =====")
            message = f"groupmsg Error: User {username} is not a member of group {group_name}."
            self.client_socket.send(message.encode())
            return

        if username not in members_joined[group_name]:
            print("===== Error: User has not joined the group. =====")
            message = f"groupmsg Error: User {username} has not joined group {group_name}."
            self.client_socket.send(message.encode())
            return

        # Handles logging
        with open(f'{group_name}_messagelog.txt', 'r') as file:
            message_number = len(file.readlines())

        with open(f'{group_name}_messagelog.txt', 'a') as file:
            timestamp = datetime.now().strftime('%d %b %Y %H:%M:%S')
            log_message = f"{message_number}; {timestamp}; {username}; {message_content}"
            file.write(log_message + "\n")

        for member in members_joined[group_name]:
            if member not in connected_clients or member == username:
                continue
            member_socket = connected_clients[member][0]
            private_message = f"groupmsg_recieve {timestamp}, {group_name}, {username}: {message_content}"
            member_socket.send(private_message.encode())

        print(f"===== Group Message on {group_name}; {message_number}; {timestamp}; {username}; {message_content}  =====")


    def handle_join_group(self, message):
        group_name = message.split(" ")[1]
        username = message.split(" ")[2]

        if group_name not in groups:
            print("===== Error: Group does not exist. =====")
            message = f"joingroup Error: Group {group_name} does not exist."
        elif username not in groups[group_name]:
            print("===== Error: User is not a member of the group. =====")
            message = f"joingroup Error: User {username} is not a member of group {group_name}."
        elif username in members_joined[group_name]:
            print("===== Error: User has already joined the group. =====")
            message = f"joingroup Error: User {username} has already joined group {group_name}."
        else:
            members_joined[group_name].append(username)
            print("===== User joined group successfully. =====")
            message = f"joingroup {group_name} joined successfully."

        self.client_socket.send(message.encode())

    def handle_create_group(self, message):
        print("===== Create group request received =====")
        group_name = message.split(" ")[1]
        group_members = message.split(" ")[2:]

        # Error handling
        if not group_name.isalnum():
            print("===== Error: Group name must only consist of letter a-z and digit 0-9. =====")
            message = f"creategroup Error: Group {group_name} creation failed. Group name must only consist of letter a-z and digit 0-9."
            self.client_socket.send(message.encode())
            return
        if group_name in groups:
            print("===== Error: Group name already exists. =====")
            message = f"creategroup Error: Group {group_name} creation failed. Group name already exists."
            self.client_socket.send(message.encode())
            return
        for member in group_members:
            if member not in connected_clients:
                print("===== Error: User is not valid or not online. =====")
                message = f"creategroup Error: Group {group_name} creation failed. User {member} is not valid or not online."
                self.client_socket.send(message.encode())
                return

        # Update groups and members_joined
        groups[group_name] = group_members
        members_joined[group_name] = [group_members[0]]

        message = f"Group {group_name} created successfully. Group members: {' '.join(group_members)}"
        self.client_socket.send(message.encode())
        print(f"===== Group {group_name} created successfully. Group members: {' '.join(group_members)} =====")
        
        # Handles logging
        with open(f"{group_name}_messagelog.txt", 'a') as file:
            log_message = f"{group_name}; {' '.join(group_members)}"
            file.write(log_message + "\n")


    def handle_active_user(self):
        print("===== Active user request received =====")

        if len(connected_clients) < 2:
            message = "activeuser No other active users."
            self.client_socket.send(message.encode())
            print("===== No other active users. =====")
            return

        # In order to incorporate multiple users in a single message to avoid the 'enter command' prompt from
        # printing again at the client side we send the message using a single string
        message = 'activeuser '
        for username in connected_clients:
            client_socket, timestamp, ip_address, udp_port = connected_clients[username]
            if client_socket != self.client_socket:
                message += f"{username}; {ip_address}; {udp_port}; active since {timestamp}.\n"
                print(f"===== {username}; {ip_address}; {udp_port}; active since {timestamp}. =====")
                
        self.client_socket.send(message.encode())

    def handle_msg_to(self, message):
        sender_username = message.split(" ")[1]
        recipient_username = message.split(" ")[2]
        message_content = " ".join(message.split(" ")[3:])
        timestamp = datetime.now().strftime('%d %b %Y %H:%M:%S')

        if sender_username == recipient_username:
            error_message = f"msg_sent Error: User {sender_username} cannot send messages to themselves."
            print("===== Error:User cannot send messages to themselves. =====")
            self.client_socket.send(error_message.encode())
            return

        if recipient_username in connected_clients:
            recipient_socket = connected_clients[recipient_username][0]
            private_message = f"msg_recieve {timestamp}, {sender_username}: {message_content}"
            recipient_socket.send(private_message.encode())
            confirmation_message = f"msg_sent message sent at {timestamp}"
            
            # Sends message confirmation to sender
            self.client_socket.send(confirmation_message.encode())
            print(f"===== {sender_username} sent a message to {recipient_username} \"{message}\" at {timestamp} =====")
            
            # Handles logging
            if os.path.isfile('messagelog.txt'):
                with open('messagelog.txt', 'r') as file:
                    message_number = len(file.readlines())
                message_number += 1
            else:
                message_number = 1
            with open("messagelog.txt", 'a') as file:
                log_message = f"{message_number}; {timestamp}; {sender_username}; {message_content}"
                file.write(log_message + "\n")
        else:
            error_message = f"msgto Error: User {recipient_username} is not online."
            print(f"===== Error: User {recipient_username} is not online. =====")
            self.client_socket.send(error_message.encode())


    def handle_user_log(self, message):
        username = message.split(" ")[1]
        client_udp_port = int(message.split(" ")[2].strip())
        timestamp = datetime.now().strftime('%d %b %Y %H:%M:%S')
        if os.path.isfile('userlog.txt'):
            with open('userlog.txt', 'r') as file:
                active_user = len(file.readlines())
            active_user += 1
        else:
            active_user = 1
        log_message = f"{active_user}; {timestamp}; {username}; {self.client_address[0]}; {client_udp_port}"
        with open('userlog.txt', 'a') as file:
            file.write(log_message + "\n")


    def authenticate(self, message):
        print('===== Authentication request received =====')
        input_username = message.split(" ")[1].strip()
        input_password = message.split(" ")[2].strip()
        client_udp_port = int(message.split(" ")[3].strip())
        
        # This block deals with blocked clients
        if input_username in blocked_clients:
            blocking_end_time = blocked_clients[input_username]
            current_time = time.time()
            if current_time < blocking_end_time:
                message = "client blocked"
                print(f"===== Error: User {input_username} is blocked. =====")
                self.client_socket.send(message.encode())
                return
            else:
                del invalid_attempts[input_username]  # reset invalid attempts
                del blocked_clients[input_username]  # reset blocked clients
        
        # This block deals with logging as well as a successful login
        does_username_exist = False
        with open("credentials.txt", 'r') as file:
            for line in file:
                username, password = map(str.strip, line.split(" "))
                if input_username == username:
                    does_username_exist = True
                    if input_password == password:
                        message = "login success"
                        print(f"===== User {input_username} logged in successfully. =====")
                        self.client_socket.send(message.encode())
                        timestamp = datetime.now().strftime('%d %b %Y %H:%M:%S')
                        connected_clients[input_username] = [self.client_socket, timestamp, self.client_address[0], client_udp_port]
                        return
        
        # This block deals with invalid login attempts (wrong password)
        if does_username_exist:
            if input_username in invalid_attempts:
                invalid_attempts[input_username] += 1
            else:
                invalid_attempts[input_username] = 1

            # Handles locking of an account when max_invalid_attempts is reached
            if invalid_attempts[input_username] >= max_invalid_attempts:
                message = "account locked"
                print(f"===== Error: User {input_username} is locked. =====")
                self.client_socket.send(message.encode())
                self.client_alive = False
                blocking_end_time = time.time() + 10
                blocked_clients[input_username] = blocking_end_time
                return
        
        # This case occurs when the username does not exist or when password is incorrect but not enough to lock the account
        message = "login failed"
        print(f"===== Error: User {input_username} failed to log in. =====")
        self.client_socket.send(message.encode())

print("\n===== Server is running =====")

while True:
    server_tcp_socket.listen()
    client_socket, client_address = server_tcp_socket.accept()
    clientThread = ClientThread(client_address, client_socket)
    clientThread.start()