export default class File {

    public filenode: HTMLInputElement | null = null;

    constructor() { }

    private createInput(opts: any = {}) {
        const input = document.createElement('input');
        input.type = 'file';
        if (opts.accept) input.accept = opts.accept;
        if (opts.multiple) input.multiple = true;
        return input;
    }

    private createFolderInput() {
        const input = document.createElement('input');
        input.type = 'file';
        input.multiple = true;
        input.setAttribute('webkitdirectory', '');
        input.setAttribute('mozdirectory', '');
        input.setAttribute('msdirectory', '');
        input.setAttribute('odirectory', '');
        input.setAttribute('directory', '');
        return input;
    }

    private parseUploadResponse(xhr: XMLHttpRequest) {
        const text = xhr.responseText || '';
        try {
            return JSON.parse(text);
        } catch (error) {
            if (xhr.status !== 200) {
                return { code: xhr.status, data: text || xhr.statusText };
            }
            return text;
        }
    }

    public async resize(file, width, quality) {
        let fn: any = () => new Promise((resolve) => {
            if (!quality) quality = 0.8;
            if (!width) width = 64;

            let output = function (canvas, callback) {
                let blob = canvas.toDataURL('image/png', quality);
                callback(blob);
            }

            let _resize = function (dataURL, maxSize, callback) {
                let image = new Image();

                image.onload = function () {
                    let canvas = document.createElement('canvas'),
                        width = image.width,
                        height = image.height;
                    if (width > height) {
                        if (width > maxSize) {
                            height *= maxSize / width;
                            width = maxSize;
                        }
                    } else {
                        if (height > maxSize) {
                            width *= maxSize / height;
                            height = maxSize;
                        }
                    }
                    canvas.width = width;
                    canvas.height = height;
                    canvas.getContext('2d').drawImage(image, 0, 0, width, height);
                    output(canvas, callback);
                };

                image.onerror = function () {
                    return;
                };

                image.src = dataURL;
            };

            let photo = function (file, maxSize, callback) {
                let reader = new FileReader();
                reader.readAsDataURL(file);
                reader.onload = function (readerEvent) {
                    _resize(readerEvent.target.result, maxSize, callback);
                };
            }

            photo(file, width, (blob) => {
                resolve(blob);
            });
        });

        return await fn();
    }

    public async upload(url: string, fd: any, callback: any = null) {
        let uploader = () => new Promise((resolve) => {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', url, true);

            xhr.upload.addEventListener('progress', async (event) => {
                let percent = 0;
                let position = event.loaded;
                let total = event.total;
                if (event.lengthComputable) {
                    percent = Math.round(position / total * 10000) / 100;
                    if (callback) await callback(percent, total, position);
                }
            }, false);

            xhr.onload = () => {
                resolve(this.parseUploadResponse(xhr));
            };

            xhr.onerror = () => {
                resolve({ code: 500, data: xhr.statusText || 'Network Error' });
            };

            xhr.send(fd);
        });
        return await uploader();
    }

    public async drop($event) {
        $event.preventDefault();
        let getFilesWebkitDataTransferItems = (dataTransferItems) => {
            let files = [];

            function traverseFileTreePromise(item, path = '') {
                return new Promise(resolve => {
                    if (item.isFile) {
                        item.file(file => {
                            file.filepath = path + file.name //save full path
                            files.push(file)
                            resolve(file)
                        })
                    } else if (item.isDirectory) {
                        let dirReader = item.createReader();
                        const entriesPromises = [];
                        const readEntriesHandler = (entries) => {
                            if (entries.length === 0) {
                                resolve(Promise.all(entriesPromises));
                                return;
                            }
                            for (let entr of entries)
                                entriesPromises.push(traverseFileTreePromise(entr, path + item.name + "/"))
                            dirReader.readEntries(readEntriesHandler);
                        }
                        dirReader.readEntries(readEntriesHandler);
                    }
                })
            }

            return new Promise((resolve, reject) => {
                let entriesPromises = []
                for (let it of dataTransferItems)
                    entriesPromises.push(traverseFileTreePromise(it.webkitGetAsEntry()));

                Promise.all(entriesPromises)
                    .then(entries => {
                        resolve(files);
                    })
            })
        }

        return await getFilesWebkitDataTransferItems($event.dataTransfer.items);
    }

    public createFilenode(uopts: any = {}) {
        delete this.filenode;
        let opts: any = {
            accept: null,
            multiple: true
        };

        for (let key in uopts) {
            opts[key] = uopts[key];
        }

        return this.createInput(opts);
    }

    public async select(uopts: any = {}) {
        delete this.filenode;
        let opts: any = {
            type: 'file',
            accept: null,
            multiple: true
        };

        for (let key in uopts) {
            opts[key] = uopts[key];
        }

        let filenode = this.filenode = opts.type == 'folder' ? this.createFolderInput() : this.createInput(opts);

        let fn: any = () => new Promise((resolve) => {
            filenode.addEventListener('change', async () => {
                let res = filenode.files;
                filenode.remove();
                delete this.filenode;
                resolve(res);
            }, { once: true });

            filenode.click();
        });

        return await fn();
    }

    public async read(uopts: any = {}) {
        delete this.filenode;
        let opts: any = {
            type: 'text',  // text, image, json
            accept: null,
            multiple: null,
            width: 512,     // if image type
            quality: 0.8   // if image type
        };

        for (let key in uopts) {
            opts[key] = uopts[key];
        }

        let filenode = this.filenode = this.createInput(opts);

        let result: any = {};

        result.text = () => new Promise((resolve) => {
            let targetLoader = (target) => new Promise((_resolve) => {
                let fr = new FileReader();
                fr.onload = async () => {
                    _resolve(fr.result);
                };
                fr.readAsText(target);
            });

            let loader = async () => {
                if (opts.multiple) {
                    let result = [];
                    let files = filenode.files;
                    for (let i = 0; i < files.length; i++)
                        result.push(await targetLoader(files[i]));
                    return resolve(result);
                }

                resolve(await targetLoader(filenode.files[0]));
            }

            loader();
        });

        result.json = () => new Promise((resolve) => {
            let targetLoader = (target) => new Promise((_resolve) => {
                let fr = new FileReader();
                fr.onload = async () => {
                    let data: any = fr.result;
                    data = JSON.parse(data);
                    _resolve(data);
                };
                fr.readAsText(target);
            });

            let loader = async () => {
                if (opts.multiple) {
                    let result = [];
                    let files = filenode.files;
                    for (let i = 0; i < files.length; i++)
                        result.push(await targetLoader(files[i]));
                    return resolve(result);
                }

                resolve(await targetLoader(filenode.files[0]));
            }

            loader();
        });

        result.image = async () => {
            let ifn: any = () => new Promise((resolve, reject) => {
                let file = filenode.files[0];
                if (!opts.width) opts.width = 512;
                if (!opts.quality) opts.quality = 0.8;
                if (opts.limit) {
                    if (file.size > opts.limit) {
                        reject("Exceeded maximum file size");
                    }
                }
                resolve(file);
            });

            let file: any = await ifn();
            file = await this.resize(file, opts.width, opts.quality);
            return file;
        }

        if (!result[opts.type]) opts.type = 'text';

        let fn: any = () => new Promise((resolve) => {
            filenode.addEventListener('change', async () => {
                let res = await result[opts.type]();
                filenode.remove();
                delete this.filenode;
                resolve(res);
            }, { once: true });

            filenode.click();
        });

        return await fn();
    }

    public async download(exportObj: any, exportName: string) {
        if (!exportName) exportName = 'download.json';
        let dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportObj));
        let downloadAnchorNode = document.createElement('a');
        downloadAnchorNode.setAttribute("href", dataStr);
        downloadAnchorNode.setAttribute("download", exportName);
        document.body.appendChild(downloadAnchorNode);
        downloadAnchorNode.click();
        downloadAnchorNode.remove();
    }

}
