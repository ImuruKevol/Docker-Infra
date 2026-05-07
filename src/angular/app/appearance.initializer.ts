import { APP_INITIALIZER } from '@angular/core';
import { AppearanceRuntime } from '@wiz/libs/portal/season/appearance';

export function initializeAppearance() {
    return async () => {
        await AppearanceRuntime.load();
    };
}

export const APPEARANCE_INITIALIZER_PROVIDER = {
    provide: APP_INITIALIZER,
    useFactory: initializeAppearance,
    multi: true
};
