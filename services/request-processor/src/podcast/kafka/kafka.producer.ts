import { Injectable, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { Kafka, Producer } from 'kafkajs';

/**
 * KafkaProducer (Observer pattern — publisher side).
 * Maintains a single long-lived producer connection.  Command handlers call
 * `publish()` without knowing anything about the transport mechanism.
 */
@Injectable()
export class KafkaProducer implements OnModuleInit, OnModuleDestroy {
  private readonly kafka: Kafka;
  private readonly producer: Producer;

  constructor() {
    const broker = process.env.KAFKA_BROKER ?? 'kafka:9092';
    this.kafka = new Kafka({
      clientId: 'request-processor-producer',
      brokers: [broker],
    });
    this.producer = this.kafka.producer();
  }

  async onModuleInit(): Promise<void> {
    await this.producer.connect();
  }

  async publish(topic: string, message: object): Promise<void> {
    await this.producer.send({
      topic,
      messages: [{ value: JSON.stringify(message) }],
    });
  }

  async onModuleDestroy(): Promise<void> {
    await this.producer.disconnect();
  }
}
