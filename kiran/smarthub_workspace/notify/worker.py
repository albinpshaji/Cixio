import pika
import json
import time
import psycopg2
import os
import sys
import random
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
MAX_RETRIES = 3

# ==========================================
# --- DISPATCHERS (MOCKED FOR DEV) ---
# ==========================================

def send_email(recipient: str, message_body: str):
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    
    if not smtp_user or not smtp_pass:
        print(f"[MOCK EMAIL] To {recipient}: {message_body}")
        return

    msg = MIMEText(message_body)
    msg['Subject'] = "SmartHub Notification"
    msg['From'] = smtp_user
    msg['To'] = recipient

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, recipient, msg.as_string())
        server.quit()
        print(f"[LIVE EMAIL] Successfully dispatched to {recipient}")
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send live email: {e}")
        raise e

def send_sms(recipient: str, message_body: str):
    # Simulated SMS delivery
    print(f"[MOCK SMS] Successfully dispatched to {recipient}: {message_body}")

def send_push(recipient: str, message_body: str):
    # Simulated Push Notification (FCM/APNs)
    print(f"[MOCK PUSH] Successfully dispatched to device {recipient}: {message_body}")

def send_whatsapp(recipient: str, message_body: str):
    # Simulated WhatsApp delivery
    print(f"[MOCK WHATSAPP] Successfully dispatched to {recipient}: {message_body}")


# ==========================================
# --- DATABASE HELPERS ---
# ==========================================

def update_job_success(job_id):
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("UPDATE notification_jobs SET sent = sent + 1 WHERE id = %s;", (job_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Database error (Success Update): {e}")

def update_job_failed(job_id):
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("UPDATE notification_jobs SET failed = failed + 1 WHERE id = %s;", (job_id,))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Database error (Failure Update): {e}")


# ==========================================
# --- QUEUE CALLBACK & ROUTING ---
# ==========================================

def callback(ch, method, properties, body):
    data = json.loads(body)
    job_id = data.get("job_id")
    task_id = data.get("task_id", "Unknown")
    recipient = data.get("recipient", "Unknown")
    message_content = data.get("message", "Default SmartHub Notification")
    
    queue_name = method.routing_key 
    if "email" in queue_name: channel_type = "Email"
    elif "sms" in queue_name: channel_type = "SMS"
    elif "push" in queue_name: channel_type = "Push"
    else: channel_type = "WhatsApp"

    headers = properties.headers or {}
    retry_count = headers.get('x-retry-count', 0)

    try:
        print(f"[job.processing] Bulk {channel_type} ({queue_name}) -> Dispatching to {recipient} (Attempt {retry_count + 1})...")
        
        # 20% random failure for chaos testing (So we can test the DLQ without real APIs failing)
        if random.random() < 0.20:
            raise Exception("Random simulated network timeout!")

        # Route to the correct dispatcher
        if channel_type == 'Email':
            send_email(recipient, message_content)
        elif channel_type == 'SMS':
            send_sms(recipient, message_content)
        elif channel_type == 'Push':
            send_push(recipient, message_content)
        else:
            send_whatsapp(recipient, message_content)
        
        time.sleep(0.5) # Slight delay so the terminal doesn't blur past instantly
        update_job_success(job_id)
        print(f"[job.success] Sent {task_id}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"[job.error] {channel_type} Task {task_id} Failed: {str(e)}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

        # 1min, 5min, 30min delays in milliseconds (as per project spec)
        delay_schedule = { 1: 60000, 2: 300000, 3: 1800000 }

        if retry_count < MAX_RETRIES:
            next_attempt = retry_count + 1
            delay_ms = delay_schedule[next_attempt]
            
            print(f"[job.retry] Task {task_id} sleeping for {delay_ms/1000} seconds. Attempt {next_attempt + 1} pending.")
            headers['x-retry-count'] = next_attempt
            
            target_retry_queue = f"{channel_type.lower()}.retry" 
            
            # Send to the holding queue where RabbitMQ will wait for 'expiration' milliseconds
            ch.basic_publish(
                exchange='',
                routing_key=target_retry_queue, 
                properties=pika.BasicProperties(
                    headers=headers,
                    expiration=str(delay_ms)
                ),
                body=body
            )
        else:
            print(f"[job.deadletter] Task {task_id} exceeded MAX_RETRIES. Moving to DLQ.")
            # Send to the final graveyard queue
            ch.basic_publish(
                exchange='',
                routing_key='dlq.notifications',
                properties=pika.BasicProperties(headers=headers),
                body=body
            )
            update_job_failed(job_id)

def main():
    print("[*] Worker booting up...")
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()

    # Declare all 4 active channels
    channels = ['email', 'sms', 'push', 'whatsapp']
    for c in channels:
        channel.queue_declare(queue=f'{c}.process', durable=True)
        # Declare retry queues mapped back to their active process queues
        channel.queue_declare(queue=f'{c}.retry', durable=True, arguments={
            'x-dead-letter-exchange': '',
            'x-dead-letter-routing-key': f'{c}.process'
        })
        
    channel.queue_declare(queue='dlq.notifications', durable=True)

    print("[*] Waiting for messages across all channels. To exit press CTRL+C")
    
    channel.basic_qos(prefetch_count=1)
    for c in channels:
        channel.basic_consume(queue=f'{c}.process', on_message_callback=callback)
    
    channel.start_consuming()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(0)