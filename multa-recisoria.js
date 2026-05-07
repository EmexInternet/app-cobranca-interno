class Multa{
    constructor(){
    
    }

    gerarMulta(){
        const valor = document.getElementById('valor').value
        const dataVendaInput = document.getElementById('data').value
        const dataCancelamentoInput = document.getElementById('dataCancelamento').value
        const dataVendaMoment = moment(dataVendaInput, 'YYYY-MM-DD', true)
        const dataCancelamentoMoment = moment(dataCancelamentoInput, 'YYYY-MM-DD', true)

        if(valor !== ''  && dataVendaInput !== '' && dataVendaMoment.isValid() && dataCancelamentoMoment.isValid()){
                const data_venda = dataVendaMoment.format('DD/MM/YYYY')
                const data_cancelamento = dataCancelamentoMoment.format('DD/MM/YYYY')

                if(dataCancelamentoMoment.isAfter(dataVendaMoment)){
                    const dia_atual = data_cancelamento.split('/')[0];
                    const mes_atual = data_cancelamento.split('/')[1];
                    const ano_atual = data_cancelamento.split('/')[2];

                    const dataDaquiA12Meses = dataVendaMoment.clone().add(12, 'months').format('DD/MM/YYYY');
                    const dataFimTesteMoment = dataVendaMoment.clone().add(7, 'days')
                    const dataFimTeste = dataFimTesteMoment.format('DD/MM/YYYY')


                    if(dataCancelamentoMoment.isAfter(dataFimTesteMoment)){

                        console.log(dataFimTeste)

                        let qtd_meses_pagos = Math.round(dataCancelamentoMoment.diff(dataVendaMoment, "months"))
                        console.log(qtd_meses_pagos)
    
                    
                        const meses_restantes = 12 - qtd_meses_pagos
    
                        if(meses_restantes <= 0){
                            console.log('Cliente já saiu da fidelidade')
                            document.getElementById('mensagem').value = ''
                            alert('Cliente já saiu da fidelidade')
                        }else{
                            const calculo_multa = (Math.abs(parseFloat(valor.replace("R$", "").trim()))) / 12 * meses_restantes
    
                            let plural_singular = ''
    
                            if(meses_restantes == 1){
                                plural_singular = `${meses_restantes} MES RESTANTE`
                            }else{
                                plural_singular = `${meses_restantes} MESES RESTANTES`
                            }
    
                            console.log(calculo_multa)
    
                            document.getElementById('mensagem').value = `CALCULO DA MULTA RESCISÓRIA\n\n`+
                                                                        `DATA DE VENDA: ${data_venda}\n`+
                                                                        `DATA DE CANCELAMENTO: ${data_cancelamento}\n`+
                                                                        `VALOR DO BENEFÍCIO: ${valor}\n\n`+
                                                                        `${plural_singular} PARA O FIM DO CONTRATO FIDELIDADE\n\n`+
                                                                        `VALOR DA MULTA RESCISÓRIA: R$ ${calculo_multa.toFixed(2)}`
                        }

                    }else{
                        alert('Cliente está no período de desistência')
                        document.getElementById('mensagem').value = ''
                    }
                    
                }else{
                    alert('Data venda é maior ou igual que a data atual, por favor corrija!')
                    document.getElementById('mensagem').value = ''
                }
        }else{
            alert('Preencha os campos devidamente!')
            document.getElementById('mensagem').value = ''
        }

    }
}

var multa = new Multa()
