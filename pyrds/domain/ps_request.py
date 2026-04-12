from __future__ import annotations

from typing import Any

from pyrds.domain.models import CustomBaseModel


class HeaderContainer(CustomBaseModel):
    UniqueKey: str | None = None
    JobId: str | None = None


class LegDetails(CustomBaseModel):
    Name: str | None = None
    Identifier: str | None = None
    LegLabel: str | None = None


class MetaDataContainer(CustomBaseModel):
    Leg: LegDetails | None = None
    Leg2: LegDetails | None = None
    Identifier: str | None = None
    Status: str | None = None
    ProductCurrency: str | None = None
    ProductType: str | None = None
    RiskSection: str | None = None
    DrmProduct: str | None = None
    FoKeyword: str | None = None
    ProductIndex: str | None = None
    Direction: str | None = None
    ExpiryDate: str | None = None
    Instrument: str | None = None
    NotionalAsset: str | None = None
    NotionalBase: str | None = None
    OptionType: str | None = None
    Strike: str | None = None
    Book: str | None = None
    Cdr: str | None = None
    TradeDate: str | None = None
    Counterparty: str | None = None
    FinalCounterparty: str | None = None
    SalesName: str | None = None
    TraderName: str | None = None
    CsaIndex: str | None = None
    CsaSpread: str | None = None


class Values(CustomBaseModel):
    Values: list[str] | None = None


class ExplicitFormContainer(CustomBaseModel):
    Keys: list[str] | None = None
    ExplicitValues: list[Values] | None = None


class ImplicitFormContainer(CustomBaseModel):
    Keys: list[str] | None = None
    ImplicitValues: list[Values] | None = None


class Parameters(CustomBaseModel):
    additionalProp1: Any | None = None
    additionalProp2: Any | None = None
    additionalProp3: Any | None = None


class RiskFactorPartition(Parameters):
    pass


class Deformations(Parameters):
    pass


class CompositScenarios(Parameters):
    pass


class RiskFactorTimeSeries(Parameters):
    pass


class FrtbParameters(CustomBaseModel):
    riskFactorPartition: list[RiskFactorPartition] | None = None
    deformations: list[Deformations] | None = None
    compositScenarios: list[CompositScenarios] | None = None
    activateTminusiSerie: bool | None = None
    riskFactorTimeSeries: RiskFactorTimeSeries | None = None
    startEnv: str | None = None
    endEnv: str | None = None
    filterRiskFactors: bool | None = None
    useCompoundTypeDeformations: bool | None = None
    useInputHistoricalDatas: bool | None = None


class PsStressScenariosDeformations(Parameters):
    pass


class DataToStress(Parameters):
    pass


class Date(CustomBaseModel):
    date: str | None = None


class EndDate(CustomBaseModel):
    date: str | None = None


class PsStressScenarios(CustomBaseModel):
    name: str | None = None
    stressParameters: Parameters | None = None
    deformations: list[PsStressScenariosDeformations] | None = None
    dataToStress: list[DataToStress] | None = None


class StressVarConfig(CustomBaseModel):
    configType: str | None = None
    source: str | None = None
    configName: str | None = None
    lag: str | None = None
    endDate: EndDate | None = None
    shockSource: str | None = None
    varPeriodicity: int | None = 6
    frtbParameters: FrtbParameters | None = None
    shockType: str | None = None
    scenarioDates: list[Date] | None = None
    psStressScenarios: list[PsStressScenarios] | None = None


class UseCache(CustomBaseModel):
    tradeSet: bool | None = None
    dataSet: bool | None = None
    incrementalTradeKey: str | None = None
    staticDataKey: str | None = None
    tradeSetId: str | None = None
    marketDataSetId: str | None = None
    requestDataSetId: str | None = None


UseCash = UseCache


class InstructionOverrides(CustomBaseModel):
    instructionName: str | None = None
    toExecute: bool | None = None
    parameters: Parameters | None = None


class UseResult(CustomBaseModel):
    psKey: str | None = None
    outputName: str | None = None
    resultType: str | None = None


class MarketDataOverride(CustomBaseModel):
    marketDataType: str | None = None
    parameters: Parameters | None = None
    marketDataKey: str | None = None


class GridPricerTechnicalDetails(CustomBaseModel):
    stressVarConfig: StressVarConfig | None = None
    qmlRunner: str | None = None
    dumpQmlFolder: str | None = None
    customFilesDirectory: str | None = None
    outputCurrency: str | None = None
    cartography: str | None = None
    foCluster: str | None = None
    subtaskPolicy: str | None = None
    gridPriority: str | None = None
    analyseName: str | None = None
    projectedCartographies: list[str] | None = None
    outPutKafka: str | None = None
    logSubDirectory: str | None = None
    sufixeClientRequest: str | None = None
    psRequestKey: str | None = None
    couchbaseName: str | None = None
    compressionType: str | None = None
    marketSnap: str | None = None
    byPosition: str | None = None
    totemRiskFactor: str | None = None
    clientRequestKey: str | None = None
    customFileDb: str | None = None
    calibrationPolicy: str | None = None
    qlibVersion: str | None = None
    futurePriceFromInception: bool | None = None
    directQmlRunnerCall: bool | None = None
    parserType: str | None = None
    tradeContext: str | None = None
    gridApplication: str | None = None
    useCache: UseCache | None = None
    instructionOverrides: list[InstructionOverrides] | None = None
    useResults: list[UseResult] | None = None
    marketDataOverrides: list[MarketDataOverride] | None = None


class PsRequest(CustomBaseModel):
    header: HeaderContainer | None = None
    metaDataContainer: MetaDataContainer | None = None
    explicitFormContainer: ExplicitFormContainer | None = None
    implicitFormContainer: ImplicitFormContainer | None = None
    gridPricerTechnicalDetails: GridPricerTechnicalDetails
    valuationDate: str | None = None
    lagInDaysForBackprice: int | str | None = None
    marketDataSetIds: list[str] | None = None
    tradeSetId: str | None = None
    requestId: str | None = None
    requestDataSetId: str | None = None
    pricingParameters: Parameters | None = None
    parameters: Parameters | None = None


Leg = LegDetails
