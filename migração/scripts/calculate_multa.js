import fs from 'node:fs';
import { calculateTerminationFine } from '../multaByClientCode.js';

const rawInput = fs.readFileSync(0, 'utf-8').trim();
if (!rawInput) {
  console.error('Payload JSON nao informado para o calculo de multa.');
  process.exit(1);
}

const payload = JSON.parse(rawInput);
const result = calculateTerminationFine({
  saleDateInput: payload.saleDate,
  cancelDateInput: payload.cancelDate,
  benefitValueInput: payload.benefitValue,
});

process.stdout.write(
  JSON.stringify(
    {
      ...result,
      saleDate: payload.saleDate,
      cancelDate: payload.cancelDate,
      benefitValue: payload.benefitValue,
    },
    null,
    2,
  ),
);
