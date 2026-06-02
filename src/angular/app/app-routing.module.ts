const INDEX_PAGE = "dashboard";

import { URLPattern } from "urlpattern-polyfill";
import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

let app_routes: Routes = wiz.routes();

const ROUTE_ALIASES: Record<string, string[]> = {
    "page.services": ["services/:service_id", "services/:service_id/:detail_tab"],
    "page.servers": ["servers/:node_id", "servers/:node_id/:detail_tab"],
    "page.domains": ["domains/:zone_id"],
    "page.images": ["images/local", "images/local/:node_id", "images/harbor", "images/harbor/:project_name", "images/harbor/:project_name/:repository_name"],
    "page.macros": ["macros/:macro_id"],
    "page.operations": ["operations/:operation_id"],
    "page.system": ["system/:section", "system/:section/:subsection"],
    "page.templates": ["templates/:template_id"]
};

export class RouteInfo {
    public path: any = "";
    public segment: any = {};

    constructor() { }
}

window.WizRoute = new RouteInfo();

let patternMatcher = (pattern: any, url: any, updateRoute: boolean = true) => {
    let urlpath = url.map((x: any) => x.path).join("/");
    let testurl = 'http://test/';
    pattern = '/' + pattern;
    urlpath = testurl + urlpath;
    pattern = new URLPattern({ pathname: pattern });
    pattern = pattern.exec(urlpath)
    if (pattern && pattern.pathname) {
        let posParams = {};
        for (let key in pattern.pathname.groups) {
            if (pattern.pathname.groups[key]) {
                posParams[key] = pattern.pathname.groups[key];
            }
        }
        if (updateRoute) {
            window.WizRoute.path = url.map((x: any) => x.path).join("/");
            window.WizRoute.segment = posParams;
        }

        return { consumed: url, posParams: posParams };
    }
    return null
}

let childAliases = (child: any) => ROUTE_ALIASES[child.app_id] || [];

let childPatterns = (child: any, includeAliases: boolean = true) => {
    let patterns = [child.path];
    if (includeAliases) patterns = patterns.concat(childAliases(child));
    return patterns.filter((pattern: any) => !!pattern);
}

let childPathMatches = (child: any, url: any) => {
    return !!patternMatcher(child.path, url, false);
}

let otherChildPathMatches = (children: any[], activeChild: any, url: any) => {
    return children.some((child: any) => child !== activeChild && childPathMatches(child, url));
}

let routes: Routes = [{
    matcher: (url: any) => {
        for (let i = 0; i < app_routes.length; i++) {
            let layout = app_routes[i];
            let layout_childs = layout.children;
            for (let j = 0; j < layout_childs.length; j++) {
                let child = layout_childs[j];
                let patterns = childPatterns(child);
                for (let k = 0; k < patterns.length; k++) {
                    let matcher = patternMatcher(patterns[k], url);
                    if (matcher)
                        return null;
                }
            }
        }
        return { consumed: url, posParams: {} };
    },
    redirectTo: INDEX_PAGE
}];

for (let i = 0; i < app_routes.length; i++) {
    let layout = app_routes[i];
    let layout_component = layout.component;
    let layout_childs = layout.children;

    let router: any = {
        path: '',
        component: layout_component,
        children: []
    };

    for (let j = 0; j < layout_childs.length; j++) {
        let child = layout_childs[j];
        router.children.push({
            matcher: (url: any) => {
                let patterns = childPatterns(child, false);
                for (let k = 0; k < patterns.length; k++) {
                    let matcher = patternMatcher(patterns[k], url);
                    if (matcher) return matcher;
                }
                if (otherChildPathMatches(layout_childs, child, url)) return null;
                patterns = childAliases(child);
                for (let k = 0; k < patterns.length; k++) {
                    let matcher = patternMatcher(patterns[k], url);
                    if (matcher) return matcher;
                }
                return null;
            },
            component: child.component
        });
    }
    routes.push(router);
}

@NgModule({ imports: [RouterModule.forRoot(routes)], exports: [RouterModule] })
export class AppRoutingModule { }
