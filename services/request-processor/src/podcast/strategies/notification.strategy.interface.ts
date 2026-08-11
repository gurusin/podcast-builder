/**
 * INotificationStrategy (Strategy pattern) — abstracts the delivery mechanism
 * for status updates.  The Kafka consumer depends on this interface, not on
 * any concrete implementation, satisfying the Dependency-Inversion Principle
 * and making it trivial to swap WebSockets for SSE, push notifications, etc.
 */
export interface INotificationStrategy {
  notify(podcastId: string, status: string): Promise<void>;
}

export const NOTIFICATION_STRATEGY = 'NOTIFICATION_STRATEGY';
