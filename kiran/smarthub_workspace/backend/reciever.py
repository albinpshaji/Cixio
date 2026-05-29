import pika

# RabbitMQ Login
credentials = pika.PlainCredentials(
    'guest',
    'guest'
)

# Connection
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host='localhost',
        port=5672,
        virtual_host='/',
        credentials=credentials
    )
)

channel = connection.channel()

# Create Queue
channel.queue_declare(queue='live_chat')

print("Waiting For Messages...\n")


def receive_message(ch, method, properties, body):

    print("Received:", body.decode())


# Start Consuming
channel.basic_consume(
    queue='live_chat',
    on_message_callback=receive_message,
    auto_ack=True
)

channel.start_consuming()