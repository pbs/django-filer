const path = require('path');

module.exports = {
    entry: {
        'filer-base.bundle': './filer/static/filer/js/base.js',
    },
    output: {
        filename: '[name].js',
        path: path.resolve(__dirname, 'filer/static/filer/js/dist'),
    },
    resolve: {
        modules: ['node_modules'],
    },
};

