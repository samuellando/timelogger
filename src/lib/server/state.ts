import { State } from '$lib/types';
import type { settings, running, interval } from '$lib/types';
import Timeline  from '$lib/Timeline';
import demoTimeline from '$lib/server/demoTimelineMig.json';
import demoRunning from '$lib/server/demoRunning.json';
import demoSettings from '$lib/server/demoSettings.json';
import prisma from '$lib/server/prisma';
import { newUser } from '$lib/server/user';
import transformer from '$lib/trpc/transformer';


export async function getState(id: string, start: number, end: number): Promise<State> {
    let data
    try {
        data = await prisma.user.findUniqueOrThrow({
            select: {
                intervals: {
                    select: {
                        start: true,
                        end: true,
                        title: true,
                        id: true,
                    }
                },
                running: {
                    select: {
                        title: true,
                        start: true,
                    }
                },
                settings: {
                    select: {
                        value: true,
                    }
                }
            },
            where: {id}
        });
    } catch (e) {
        data = await newUser(id);
    }

    if (data.running == null) {
        data.running = {title: 'Nothing', start: new Date(0)};
        prisma.running.create({
            data: {userId: id, ...data.running},
        });
    }

    let settings: settings;
    if (data.settings != null) {
        settings = JSON.parse(data.settings.value);
    } else {
        settings = {};
        prisma.settings.create({
            data: {userId: id, value: JSON.stringify(settings)},
        });
    }

    return new State(new Timeline(data.intervals), data.running, settings);
}

export function getDemoState(): State {
    let timelineRaw = demoTimeline;
    let running: running = {
        title: demoRunning.title,
        start: new Date(Date.parse(demoRunning.start)),
    };
    let settings = demoSettings;

    // 10 minutes ago.
    let end = Date.now() - 10 * 60 * 1000;
    let last = Date.parse(timelineRaw[timelineRaw.length - 1].end);
    let shift = end - last;
    let timeline: interval[] = timelineRaw.map((interval) => {
        return ({
            id: interval.id,
            title: interval.title,
            start: new Date(Date.parse(interval.start) + shift),
            end: new Date(Date.parse(interval.end) + shift),
        });
    });

    running.start = new Date(end);

    return new State(new Timeline(timeline), running, settings);
}