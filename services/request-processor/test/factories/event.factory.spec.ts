import { EventFactory } from '../../src/podcast/factories/event.factory';

describe('EventFactory', () => {
  let factory: EventFactory;

  beforeEach(() => {
    // No mocks needed — EventFactory has no dependencies and uses only
    // built-in Date.  We test the pure construction logic directly.
    factory = new EventFactory();
  });

  describe('createTopicRequestedEvent', () => {
    it('should return an event with eventType TopicRequested', () => {
      const event = factory.createTopicRequestedEvent(
        'pod-id-1',
        'Climate Change',
        'short',
      );

      expect(event.eventType).toBe('TopicRequested');
    });

    it('should return an event with version 1.0', () => {
      const event = factory.createTopicRequestedEvent(
        'pod-id-1',
        'Climate Change',
        'short',
      );

      expect(event.version).toBe('1.0');
    });

    it('should echo back the supplied podcastId, topic, and durationHint', () => {
      const event = factory.createTopicRequestedEvent(
        'pod-id-42',
        'Machine Learning',
        'long',
      );

      expect(event.podcastId).toBe('pod-id-42');
      expect(event.topic).toBe('Machine Learning');
      expect(event.durationHint).toBe('long');
    });

    it('should set ts to a valid ISO 8601 string', () => {
      const beforeCall = Date.now();
      const event = factory.createTopicRequestedEvent(
        'pod-id-1',
        'History',
        'medium',
      );
      const afterCall = Date.now();

      // ts must be parseable
      const parsed = Date.parse(event.ts);
      expect(Number.isNaN(parsed)).toBe(false);

      // ts must be within the time window of the test run
      expect(parsed).toBeGreaterThanOrEqual(beforeCall);
      expect(parsed).toBeLessThanOrEqual(afterCall);
    });

    it('should produce a fresh ts on each invocation', async () => {
      const first = factory.createTopicRequestedEvent('a', 'Topic A', 'short');
      await new Promise<void>((resolve) => setTimeout(resolve, 5));
      const second = factory.createTopicRequestedEvent('b', 'Topic B', 'short');

      // ISO strings must be distinct (different moments in time)
      expect(first.ts).not.toBe(second.ts);
    });
  });
});
