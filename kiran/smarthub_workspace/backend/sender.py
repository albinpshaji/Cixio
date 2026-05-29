import pika
import time

# Connect RabbitMQ
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost')
)

channel = connection.channel()

# Create Queue
channel.queue_declare(queue='live_chat')

print("Start Sending Messages...\n")

while True:

    message = input("You: ")

    # Send Message
    channel.basic_publish(
        exchange='',
        routing_key='live_chat',
        body=message
    )

    print("Message Sent")

connection.close()