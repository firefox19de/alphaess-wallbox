const fs = require('fs');
const pkg = require('./package.json');

// config.yaml einlesen und Version ersetzen
let config = fs.readFileSync('config.yaml', 'utf8');
config = config.replace(/^version: ".*"/m, `version: "${pkg.version}"`);
fs.writeFileSync('config.yaml', config);

console.log(`Updated config.yaml to v${pkg.version}`);