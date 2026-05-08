const DEFAULT_BENEFIT_VALUE = Number(process.env.REACT_APP_MULTA_BENEFIT || 600);

const getClientByCode = async (codigoCliente) => {
  let importedModule;
  try {
    importedModule = await import('./emexApi.js');
  } catch (error) {
    throw new Error(
      'Modulo emexApi.js nao encontrado. Use calculateTerminationFine via scripts/calculate_multa.js ' +
      'ou disponibilize ./emexApi.js para o fluxo completo em Node.',
    );
  }

  if (typeof importedModule.getClientByCode !== 'function') {
    throw new Error('A funcao getClientByCode nao foi encontrada em ./emexApi.js.');
  }

  return importedModule.getClientByCode(codigoCliente);
};

const parseInputDate = (value) => {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return null;
  }

  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
};

const getTodayInputDate = () => {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const toPtBrDate = (value) => {
  if (!value) {
    return 'Data não informada';
  }

  const [year, month, day] = String(value).split('-');

  if (!year || !month || !day) {
    return value;
  }

  return `${day}/${month}/${year}`;
};

const getElapsedMonths = (saleDate, cancelDate) => {
  const yearDiff = cancelDate.getFullYear() - saleDate.getFullYear();
  const monthDiff = cancelDate.getMonth() - saleDate.getMonth();
  const dayAdjustment = cancelDate.getDate() < saleDate.getDate() ? 1 : 0;
  return Math.max(yearDiff * 12 + monthDiff - dayAdjustment, 0);
};

export const calculateTerminationFine = ({ saleDateInput, cancelDateInput, benefitValueInput }) => {
  const saleDate = parseInputDate(saleDateInput);
  const cancelDate = parseInputDate(cancelDateInput);

  if (!saleDate || !cancelDate) {
    return {
      valid: false,
      reason: 'data_invalida',
      message: 'Data de venda ou data de cancelamento inválida.',
      fineValue: 0,
      monthsRemaining: 0,
    };
  }

  if (cancelDate <= saleDate) {
    return {
      valid: false,
      reason: 'cancelamento_antes_da_venda',
      message: 'A data de cancelamento deve ser maior que a data de venda.',
      fineValue: 0,
      monthsRemaining: 0,
    };
  }

  const trialEndDate = new Date(saleDate);
  trialEndDate.setDate(trialEndDate.getDate() + 7);

  if (cancelDate <= trialEndDate) {
    return {
      valid: true,
      reason: 'periodo_desistencia',
      message: 'Cliente está no período de desistência.',
      fineValue: 0,
      monthsRemaining: 12,
      isInTrialPeriod: true,
    };
  }

  const elapsedMonths = getElapsedMonths(saleDate, cancelDate);
  const monthsRemaining = Math.max(12 - elapsedMonths, 0);

  if (monthsRemaining <= 0) {
    return {
      valid: true,
      reason: 'fora_fidelidade',
      message: 'Cliente já saiu da fidelidade.',
      fineValue: 0,
      monthsRemaining,
      isInTrialPeriod: false,
    };
  }

  const benefitValue = Number.isFinite(Number(benefitValueInput))
    ? Math.abs(Number(benefitValueInput))
    : DEFAULT_BENEFIT_VALUE;

  const fineValue = Number(((benefitValue / 12) * monthsRemaining).toFixed(2));

  return {
    valid: true,
    reason: 'multa_calculada',
    message: 'Multa calculada com sucesso.',
    fineValue,
    monthsRemaining,
    isInTrialPeriod: false,
  };
};

const buildCalculationMessage = ({ saleDate, cancelDate, benefitValue, monthsRemaining, fineValue }) => {
  const label = monthsRemaining === 1 ? '1 MÊS RESTANTE' : `${monthsRemaining} MESES RESTANTES`;

  return (
    'CALCULO DA MULTA RESCISÓRIA\n\n' +
    `DATA DE VENDA: ${toPtBrDate(saleDate)}\n` +
    `DATA DE CANCELAMENTO: ${toPtBrDate(cancelDate)}\n` +
    `VALOR DO BENEFÍCIO: R$ ${Number(benefitValue).toFixed(2)}\n\n` +
    `${label} PARA O FIM DO CONTRATO FIDELIDADE\n\n` +
    `VALOR DA MULTA RESCISÓRIA: R$ ${Number(fineValue).toFixed(2)}`
  );
};

export const calculateMultaByClientCode = async (codigoCliente, options = {}) => {
  const normalizedCode = String(codigoCliente || '').trim();

  if (!normalizedCode) {
    throw new Error('Informe um código de cliente válido.');
  }

  const customer = await getClientByCode(normalizedCode);
  const services = Array.isArray(customer?.servicos) ? customer.servicos : [];

  if (services.length === 0) {
    throw new Error('Cliente encontrado, mas sem serviços para cálculo.');
  }

  const benefitValue = Number.isFinite(Number(options.benefitValue))
    ? Number(options.benefitValue)
    : DEFAULT_BENEFIT_VALUE;

  const forcedCancelDate = options.cancelDate || null;

  const calculations = services.map((service) => {
    const saleDate = service?.dataVenda || '';
    const cancelDate = forcedCancelDate || service?.dataCancelamentoCalculo || getTodayInputDate();

    const result = calculateTerminationFine({
      saleDateInput: saleDate,
      cancelDateInput: cancelDate,
      benefitValueInput: benefitValue,
    });

    const fineMessage = result.valid && result.fineValue > 0
      ? buildCalculationMessage({
          saleDate,
          cancelDate,
          benefitValue,
          monthsRemaining: result.monthsRemaining,
          fineValue: result.fineValue,
        })
      : result.message;

    return {
      serviceId: service?.id || '',
      planName: service?.nomePlano || '',
      serviceStatus: service?.status || '',
      saleDate,
      cancelDate,
      benefitValue,
      ...result,
      fineMessage,
    };
  });

  const selectedServiceId = options.serviceId ? String(options.serviceId) : '';
  const selectedCalculation =
    calculations.find((item) => item.serviceId === selectedServiceId) ||
    calculations.find((item) => item.fineValue > 0) ||
    calculations[0];

  return {
    customerCode: customer?.codigoCliente || normalizedCode,
    customerName: customer?.nome || '',
    selectedCalculation,
    calculations,
  };
};

export const getFineValueByClientCode = async (codigoCliente, options = {}) => {
  const result = await calculateMultaByClientCode(codigoCliente, options);
  return Number(result?.selectedCalculation?.fineValue || 0);
};

export default calculateMultaByClientCode;
