import { afterEach, describe, expect, it, vi } from "vitest";
import {
  consumeRateLimit,
  createCabinSession,
  createSunroofConfirmation,
  isBrowserLocation,
  takeSunroofConfirmation,
} from "../cabinSession";

afterEach(() => {
  vi.useRealTimers();
});

describe("cabin session state", () => {
  it.each([
    ["default", 82, 20],
    ["rain", 0, 70],
    ["moving", 35, 20],
  ] as const)("creates an isolated %s scenario", (scenario, speed, rainProbability) => {
    const session = createCabinSession(scenario);
    expect(session.vehicle.speed).toBe(speed);
    expect(session.vehicle.rainProbability).toBe(rainProbability);
  });

  it("stores an explicitly supplied browser location", () => {
    const session = createCabinSession("default", {
      latitude: 31.2304,
      longitude: 121.4737,
      accuracyMeters: 18,
      allowExternalRouting: true,
    });
    expect(session.vehicle).toMatchObject({
      latitude: 31.2304,
      longitude: 121.4737,
      locationSource: "browser_geolocation",
      locationAccuracyMeters: 18,
      externalRoutingConsent: true,
    });
  });

  it("validates browser location ranges and extra fields", () => {
    expect(isBrowserLocation({ latitude: 31, longitude: 121 })).toBe(true);
    expect(isBrowserLocation({ latitude: 31, longitude: 121, allowExternalRouting: true })).toBe(true);
    expect(isBrowserLocation({ latitude: 31, longitude: 121, allowExternalRouting: "yes" })).toBe(false);
    expect(isBrowserLocation({ latitude: 91, longitude: 121 })).toBe(false);
    expect(isBrowserLocation({ latitude: 31, longitude: 121, trusted: true })).toBe(false);
  });

  it("consumes a high-speed confirmation only once", () => {
    const session = createCabinSession();
    createSunroofConfirmation(session, 50);
    expect(takeSunroofConfirmation(session)?.targetPercent).toBe(50);
    expect(takeSunroofConfirmation(session)).toBeNull();
  });

  it("expires a pending confirmation after two minutes", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-11T00:00:00Z"));
    const session = createCabinSession();
    createSunroofConfirmation(session, 30);
    vi.advanceTimersByTime(2 * 60 * 1000 + 1);
    expect(takeSunroofConfirmation(session)).toBeNull();
  });

  it("rejects the 31st request in one rate window", () => {
    const key = `test-${crypto.randomUUID()}`;
    for (let index = 0; index < 30; index += 1) {
      expect(consumeRateLimit(key).allowed).toBe(true);
    }
    expect(consumeRateLimit(key).allowed).toBe(false);
  });
});
