import { Injectable, Logger, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { Kafka, Producer } from 'kafkajs';

@Injectable()
export class KafkaProducer implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(KafkaProducer.name);
  private readonly kafka: Kafka;
  private readonly producer: Producer;
  private connected = false;

  constructor() {
    const broker = process.env.KAFKA_BROKER ?? 'kafka:9092';
    this.kafka = new Kafka({
      clientId: 'request-processor-producer',
      brokers: [broker],
      retry: { retries: 5, initialRetryTime: 300 },
    });
    this.producer = this.kafka.producer();
  }

  async onModuleInit(): Promise<void> {
    await this.connectWithRetry();
  }

  async publish(topic: string, message: object): Promise<void> {
    if (!this.connected) {
      await this.connectWithRetry();
    }
    await this.producer.send({
      topic,
      messages: [{ value: JSON.stringify(message) }],
    });
  }

  async onModuleDestroy(): Promise<void> {
    if (this.connected) {
      await this.producer.disconnect();
    }
  }

  private async connectWithRetry(attempts = 10, delayMs = 3000): Promise<void> {
    for (let i = 1; i <= attempts; i++) {
      try {
        await this.producer.connect();
        this.connected = true;
        this.logger.log('Kafka producer connected');
        return;
      } catch (err) {
        this.logger.warn(`Kafka producer connect attempt ${i}/${attempts} failed: ${(err as Error).message}`);
        if (i < attempts) await this.delay(delayMs);
      }
    }
    // All retries exhausted — log and continue so HTTP server still starts.
    // publish() will reattempt connection on first request.
    this.logger.error('Kafka producer could not connect after all retries — HTTP server will start anyway');
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
