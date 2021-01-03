export const pad = (n: number, max: number, v: string = "0") => (n + '').padStart(max, v);

export function durationToTimer(start: Date, end: Date) {
    // Difference in milliseconds
    const difference = end.valueOf() - start.valueOf();

    const seconds = pad(Math.floor((difference % (1000 * 60)) / 1000), 2);
    const minutes = pad(Math.floor((difference % (1000 * 60 * 60)) / (1000 * 60)), 2);
    const hours = Math.floor((difference % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));

    if (difference < 0) {
        return `-${hours}:${minutes}:${seconds}`;
    } else {
        return `${hours}:${minutes}:${seconds}`;
    }
}