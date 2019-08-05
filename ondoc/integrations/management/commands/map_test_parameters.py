from django.core.management import BaseCommand
from ondoc.integrations.Integrators import Thyrocare
from django.conf import settings
from ondoc.integrations.models import IntegratorLabTestParameterMapping


def map_test_parameters():

    integrator_test_codes = ["%TSA", "A/GR", "ABAS", "ABAS", "ABAS", "ABAS", "ABAS", "ABAS", "ABAS", "ABAS", "ABAS", "ABAS", "ABAS",
          "ABAS", "ABAS", "ABAS", "ABAS", "ABAS", "ABAS", "ABAS", "ABAS", "ABAS", "ABAS", "ABAS", "ABG", "AC_A", "AC_G",
          "AC_M", "ACAG", "ACAM", "ACCP", "ACD3", "ACD3", "ACD4", "ACD4", "ACD8", "ACD8", "ACETA", "ADA", "AEOS",
          "AEOS", "AEOS", "AEOS", "AEOS", "AEOS", "AEOS", "AEOS", "AEOS", "AEOS", "AEOS", "AEOS", "AEOS", "AEOS",
          "AEOS", "AEOS", "AEOS", "AEOS", "AEOS", "AEOS", "AEOS", "AEOS", "AFP", "AHBE", "AHCV", "ALKP", "ALR01",
          "ALR02", "ALR03", "ALR04", "ALR05", "ALR06", "ALR07", "ALR08", "ALR09", "ALR10", "ALR11", "ALR12", "ALR13",
          "ALR14", "ALR15", "ALR16", "ALR17", "ALR18", "ALR19", "ALYM", "ALYM", "ALYM", "ALYM", "ALYM", "ALYM", "ALYM",
          "ALYM", "ALYM", "ALYM", "ALYM", "ALYM", "ALYM", "ALYM", "ALYM", "ALYM", "ALYM", "ALYM", "ALYM", "ALYM",
          "ALYM", "ALYM", "ALYMP", "AMA", "AMH", "AMH", "AMH", "AMH", "AMH", "AMH", "AMH", "AMON", "AMON", "AMON",
          "AMON", "AMON", "AMON", "AMON", "AMON", "AMON", "AMON", "AMON", "AMON", "AMON", "AMON", "AMON", "AMON",
          "AMON", "AMON", "AMON", "AMON", "AMON", "AMON", "AMPHE", "AMXD", "AMYL", "ANA", "ANDR", "ANDR", "ANEU",
          "ANEU", "ANEU", "ANEU", "ANEU", "ANEU", "ANEU", "ANEU", "ANEU", "ANEU", "ANEU", "ANEU", "ANEU", "ANEU",
          "ANEU", "ANEU", "ANEU", "ANEU", "ANEU", "ANEU", "ANEU", "ANEU", "APB/", "APB/", "APLG", "APLM", "APOA",
          "APOA", "APOB", "APOB", "ARCT3", "ARCT4", "ASAB", "ASO", "ATG", "B/CR", "B2G1G", "B2G1M", "BARBI", "BASO",
          "BASO", "BASO", "BASO", "BASO", "BASO", "BASO", "BASO", "BASO", "BASO", "BASO", "BASO", "BASO", "BASO",
          "BASO", "BASO", "BASO", "BASO", "BASO", "BASO", "BASO", "BASO", "BENZO", "BILD", "BILI", "BILT", "BKETO",
          "BTEAG", "BTEAL", "BTEAS", "BTEBA", "BTEBE", "BTEBI", "BTECD", "BTECO", "BTECR", "BTECS", "BTEHG", "BTELI",
          "BTEMN", "BTEMO", "BTENI", "BTEPB", "BTESB", "BTESE", "BTESN", "BTESR", "BTETL", "BTEU", "BTEV", "BUN",
          "C125", "C153", "C199", "C3", "C4", "CALC", "CANC", "CANNA", "CD3", "CD3", "CD4", "CD4", "CD8", "CD8", "CEA",
          "CERU", "CHL", "CHL_G", "CHL_M", "CHOL", "CM_G", "CM_M", "COCAI", "CPEP", "CRP", "CYST", "CYST", "DG_G",
          "DG_M", "DGP-A", "DGP-G", "DHEA", "DHEA", "DHEA", "DHEA", "DHEA", "DHEA", "DHEA", "DHEA", "DHEA", "DHEA",
          "DHEA", "DHEA", "DHEA", "DHEA", "DNA", "EAG", "EBVCG", "EBVCM", "EBVNG", "EGFR", "EOS", "EOS", "EOS", "EOS",
          "EOS", "EOS", "EOS", "EOS", "EOS", "EOS", "EOS", "EOS", "EOS", "EOS", "EOS", "EOS", "EOS", "EOS", "EOS",
          "EOS", "EOS", "EOS", "ERYP", "ESR", "ESR", "ETHYL", "FBS", "FERR", "FERR", "FERR", "FERR", "FOLI", "FPSA",
          "FRUCT", "FSH", "FT3", "FT3", "FT4", "FT4", "FTES", "FTES", "FTES", "FTES", "FTES", "FTES", "FTES", "FTES",
          "G6PD", "GBMG", "GENTA", "GGT", "GGT", "GRAN", "HAVM", "HAVT", "HB", "HB", "HB", "HB", "HB", "HB", "HB", "HB",
          "HB", "HB", "HB", "HB", "HB", "HB", "HB", "HB", "HB", "HB", "HB", "HB", "HB", "HB", "HBA", "HBCM", "HBCT",
          "HBST", "HC_G", "HC_M", "HCHO", "HEAL", "HEAS", "HEBA", "HEBI", "HECA", "HECD", "HECO", "HECR", "HECS",
          "HECU", "HEFE", "HEHG", "HEK", "HELI", "HEMB", "HEMG", "HEMN", "HENA", "HENI", "HEPB", "HESB", "HESE", "HESN",
          "HEU", "HEVM", "HEZN", "HGH", "HGH", "HIVE", "HIVE2", "HOMO", "HPYA", "HPYG", "HS1G", "HS1M", "HS2G", "HS2M",
          "HSCRP", "IG", "IG", "IG", "IG", "IG", "IG", "IG", "IG", "IG", "IG", "IG", "IG", "IG", "IG", "IG", "IG", "IG",
          "IG", "IG", "IG", "IG", "IG", "IG%", "IG%", "IG%", "IG%", "IG%", "IG%", "IG%", "IG%", "IG%", "IG%", "IG%",
          "IG%", "IG%", "IG%", "IG%", "IG%", "IG%", "IG%", "IG%", "IG%", "IG%", "IG%", "IGA", "IGG", "IGM", "IGP",
          "IRON", "IRON", "KKK01", "LASE", "LCVDT", "LDH", "LDL", "LDL/", "LDLC", "LEUC", "LEUC", "LEUC", "LEUC",
          "LEUC", "LEUC", "LEUC", "LEUC", "LEUC", "LEUC", "LEUC", "LEUC", "LEUC", "LEUC", "LEUC", "LEUC", "LEUC",
          "LEUC", "LEUC", "LEUC", "LEUC", "LEUC", "LH", "LITHI", "LKM1", "LP_M", "LPA", "LYMPH", "LYMPH", "LYMPH",
          "LYMPH", "LYMPH", "LYMPH", "LYMPH", "LYMPH", "LYMPH", "LYMPH", "LYMPH", "LYMPH", "LYMPH", "LYMPH", "LYMPH",
          "LYMPH", "LYMPH", "LYMPH", "LYMPH", "LYMPH", "LYMPH", "LYMPH", "MCH", "MCH", "MCH", "MCH", "MCH", "MCH",
          "MCH", "MCH", "MCH", "MCH", "MCH", "MCH", "MCH", "MCH", "MCH", "MCH", "MCH", "MCH", "MCH", "MCH", "MCH",
          "MCH", "MCHC", "MCHC", "MCHC", "MCHC", "MCHC", "MCHC", "MCHC", "MCHC", "MCHC", "MCHC", "MCHC", "MCHC", "MCHC",
          "MCHC", "MCHC", "MCHC", "MCHC", "MCHC", "MCHC", "MCHC", "MCHC", "MCHC", "MCV", "MCV", "MCV", "MCV", "MCV",
          "MCV", "MCV", "MCV", "MCV", "MCV", "MCV", "MCV", "MCV", "MCV", "MCV", "MCV", "MCV", "MCV", "MCV", "MCV",
          "MCV", "MCV", "METHA", "MG", "MID", "MONO", "MONO", "MONO", "MONO", "MONO", "MONO", "MONO", "MONO", "MONO",
          "MONO", "MONO", "MONO", "MONO", "MONO", "MONO", "MONO", "MONO", "MONO", "MONO", "MONO", "MONO", "MONO", "MPV",
          "MPV", "MPV", "MPV", "MPV", "MPV", "MPV", "MPV", "MPV", "MPV", "MPV", "MPV", "MPV", "MPV", "MPV", "MPV",
          "MPV", "MPV", "MPV", "MPV", "MPV", "MPV", "MXD", "NEUT", "NEUT", "NEUT", "NEUT", "NEUT", "NEUT", "NEUT",
          "NEUT", "NEUT", "NEUT", "NEUT", "NEUT", "NEUT", "NEUT", "NEUT", "NEUT", "NEUT", "NEUT", "NEUT", "NEUT",
          "NEUT", "NEUT", "NHDL", "NRBC", "NRBC", "NRBC", "NRBC", "NRBC", "NRBC", "NRBC", "NRBC", "NRBC", "NRBC",
          "NRBC", "NRBC", "NRBC", "NRBC", "NRBC", "NRBC", "NRBC", "NRBC", "NRBC", "NRBC", "NRBC", "NRBC", "NRBC%",
          "NRBC%", "NRBC%", "NRBC%", "NRBC%", "NRBC%", "NRBC%", "NRBC%", "NRBC%", "NRBC%", "NRBC%", "NRBC%", "NRBC%",
          "NRBC%", "NRBC%", "NRBC%", "NRBC%", "NRBC%", "NRBC%", "NRBC%", "NRBC%", "NRBC%", "NRBCP", "NS1", "OPIAT",
          "PANC", "PAPPA", "PAPPA", "PAPPA", "PAPPA", "PAPPA", "PCT", "PCT", "PCT", "PCT", "PCT", "PCT", "PCT", "PCT",
          "PCT", "PCT", "PCT", "PCT", "PCT", "PCT", "PCT", "PCT", "PCT", "PCT", "PCT", "PCT", "PCT", "PCT", "PCV",
          "PCV", "PCV", "PCV", "PCV", "PCV", "PCV", "PCV", "PCV", "PCV", "PCV", "PCV", "PCV", "PCV", "PCV", "PCV",
          "PCV", "PCV", "PCV", "PCV", "PCV", "PCV", "PDW", "PDW", "PDW", "PDW", "PDW", "PDW", "PDW", "PDW", "PDW",
          "PDW", "PDW", "PDW", "PDW", "PDW", "PDW", "PDW", "PDW", "PDW", "PDW", "PDW", "PDW", "PDW", "PHBAR", "PHEN",
          "PHENC", "PHOS", "PHOS", "PLA2", "PLCR", "PLCR", "PLCR", "PLCR", "PLCR", "PLCR", "PLCR", "PLCR", "PLCR",
          "PLCR", "PLCR", "PLCR", "PLCR", "PLCR", "PLCR", "PLCR", "PLCR", "PLCR", "PLCR", "PLCR", "PLCR", "PLCR", "PLT",
          "PLT", "PLT", "PLT", "PLT", "PLT", "PLT", "PLT", "PLT", "PLT", "PLT", "PLT", "PLT", "PLT", "PLT", "PLT",
          "PLT", "PLT", "PLT", "PLT", "PLT", "PLT", "PNL01", "PNL01A", "PNL01B", "PNL01C", "PNL01D", "PNL02", "PNL02A",
          "PNL02B", "PNL02C", "PNL02D", "PNL02E", "PNL02F", "PNL03", "PNL03A", "PNL03B", "PNL03C", "PNL03D", "PNL03E",
          "PNL03F", "PNL04", "PNL04A", "PNL04B", "PNL04C", "PNL04D", "PNL04E", "PNL05", "PNL05A", "PNL05B", "PNL05C",
          "PNL05D", "PNL05E", "PNL06", "PNL06A", "PNL06B", "PNL06C", "PNL06D", "PNL06E", "PNL06F", "PNL07", "PNL07A",
          "PNL07B", "PNL07C", "PNL07D", "PNL07E", "PNL08A", "PNL08B", "PNL08C", "PNL08D", "PNL09", "PNL09A", "PNL09B",
          "PNL09C", "PNL09D", "PNL09E", "POT", "PPBS", "PRL", "PRL", "PROT", "PSA", "PTH", "RB_G", "RB_M", "RBC", "RBC",
          "RBC", "RBC", "RBC", "RBC", "RBC", "RBC", "RBC", "RBC", "RBC", "RBC", "RBC", "RBC", "RBC", "RBC", "RBC",
          "RBC", "RBC", "RBC", "RBC", "RBC", "RBS", "RCD48", "RCD48", "RDCV", "RDCV", "RDCV", "RDCV", "RDCV", "RDCV",
          "RDCV", "RDCV", "RDCV", "RDCV", "RDCV", "RDCV", "RDCV", "RDCV", "RDCV", "RDCV", "RDCV", "RDCV", "RDCV",
          "RDCV", "RDCV", "RDCV", "RDWSD", "RDWSD", "RDWSD", "RDWSD", "RDWSD", "RDWSD", "RDWSD", "RDWSD", "RDWSD",
          "RDWSD", "RDWSD", "RDWSD", "RDWSD", "RDWSD", "RDWSD", "RDWSD", "RDWSD", "RDWSD", "RDWSD", "RDWSD", "RDWSD",
          "RDWSD", "RFAC", "SAG", "SALB", "SALIC", "SCL70", "SCRE", "SCRE", "SDLDL", "SECU", "SECU", "SEGB", "SEZN",
          "SGOT", "SGOT", "SGPT", "SGPT", "SHBG", "SHBG", "SHBG", "SHBG", "SOD", "STFR", "T3", "T3", "T4", "T4", "TB_A",
          "TB_G", "TB_M", "TC/H", "TEST", "TEST", "TEST", "TEST", "TEST", "TEST", "TEST", "TEST", "TEST", "TEST",
          "TEST", "TEST", "TEST", "TG", "THEOP", "TIBC", "TIBC", "TIGE", "TIGE", "TIGE","TIGE","TIGE","TPAB","TPHA",
          "TRI / H","TRIG","TSH","TSH","TTGA","TX_G","TX_M","UA / C","UALB","UCRA","UCRA","URIC","URIC","USTSH","UTEAS",
          "UTEBA","UTECD","UTECO","UTECR","UTECS","UTEHG","UTELI","UTEPB","VALP","VD125","VITB","VITB","VITB1","VITB2",
          "VITB3","VITB5","VITB6","VITB7","VITB9","VITDC","VITK","VLDL"]

    unique_test_paramters = list(set(integrator_test_codes))

    for parameter in unique_test_paramters:
        obj = IntegratorLabTestParameterMapping(integrator_class_name=Thyrocare.__name__, integrator_test_parameter_code=parameter)
        obj.save()


class Command(BaseCommand):
    def handle(self, **options):
        map_test_parameters()