import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { NgModule, Pipe, PipeTransform } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { FormsModule, COMPOSITION_BUFFER_MODE } from '@angular/forms';
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { RouterModule, RouterOutlet } from '@angular/router';
import { NgbModule } from '@ng-bootstrap/ng-bootstrap';
import { NuMonacoEditorComponent, provideNuMonacoEditorConfig } from '@ng-util/monaco-editor';
import { SortablejsModule } from "@wiz/libs/portal/season/ngx-sortablejs";
import { KeyboardShortcutsModule } from 'ng-keyboard-shortcuts';
import { DomSanitizer } from '@angular/platform-browser';

@Pipe({ name: 'safe' })
export class SafePipe implements PipeTransform {
    constructor(private domSanitizer: DomSanitizer) { }
    transform(url) {
        return this.domSanitizer.bypassSecurityTrustResourceUrl(url);
    }
}

// translate libs
import { TranslateLoader, TranslateModule } from '@ngx-translate/core';
import { TranslateHttpLoader, TRANSLATE_HTTP_LOADER_CONFIG } from '@ngx-translate/http-loader'

// initialize ng module
@NgModule({
    declarations: [
        SafePipe,
        '@wiz.declarations'
    ],
    imports: [
        BrowserModule,
        AppRoutingModule,
        RouterModule,
        RouterOutlet,
        FormsModule,
        NgbModule,
        SortablejsModule,
        KeyboardShortcutsModule.forRoot(),
        NuMonacoEditorComponent,
        TranslateModule.forRoot({
            loader: {
                provide: TranslateLoader,
                useClass: TranslateHttpLoader
            },
            fallbackLang: 'en'
        }),
        '@wiz.imports'
    ],
    providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideNuMonacoEditorConfig({ baseUrl: `lib` }),
        {
            provide: TRANSLATE_HTTP_LOADER_CONFIG,
            useValue: {
                prefix: './assets/lang/',
                suffix: '.json'
            }
        },
        {
            provide: COMPOSITION_BUFFER_MODE,
            useValue: false
        }
    ],
    bootstrap: [AppComponent]
})
export class AppModule { }
