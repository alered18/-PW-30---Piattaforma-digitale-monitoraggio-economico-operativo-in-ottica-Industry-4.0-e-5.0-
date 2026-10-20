"""Tabelle del database mappate con SQLAlchemy.

Lo schema vero è definito in database/init/01_schema.sql: queste classi lo descrivono per poterlo interrogare
da Python e devono restare allineate allo script (i test d'integrazione girano sullo schema reale).
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Computed, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Linea(Base):
    __tablename__ = "linea"

    id: Mapped[int] = mapped_column(primary_key=True)
    codice: Mapped[str]
    nome: Mapped[str]
    macchine: Mapped[list["Macchina"]] = relationship(back_populates="linea", order_by="Macchina.ordine")


class Macchina(Base):
    __tablename__ = "macchina"

    id: Mapped[int] = mapped_column(primary_key=True)
    linea_id: Mapped[int] = mapped_column(ForeignKey("linea.id"))
    codice: Mapped[str]
    nome: Mapped[str]
    ordine: Mapped[int]
    capacita_conf_h: Mapped[Decimal]
    # Calcolato dal database (3600 / capacità): non va mai scritto.
    tempo_ciclo_ideale_s: Mapped[Decimal] = mapped_column(Computed("3600 / capacita_conf_h"))
    potenza_funz_kw: Mapped[Decimal]
    potenza_fermo_kw: Mapped[Decimal]
    costo_orario_eur: Mapped[Decimal]
    scarto_nominale: Mapped[Decimal]
    costo_scarto_eur_conf: Mapped[Decimal]
    linea: Mapped[Linea] = relationship(back_populates="macchine")


class CausaleFermo(Base):
    __tablename__ = "causale_fermo"

    codice: Mapped[str] = mapped_column(primary_key=True)
    descrizione: Mapped[str]
    pianificata: Mapped[bool]


class Rilevazione(Base):
    __tablename__ = "rilevazione"

    id: Mapped[int] = mapped_column(primary_key=True)
    macchina_id: Mapped[int] = mapped_column(ForeignKey("macchina.id"))
    inizio: Mapped[datetime]
    durata_s: Mapped[int]
    pezzi: Mapped[int]
    scarti: Mapped[int]
    t_funz_s: Mapped[int]
    t_fermo_s: Mapped[int]
    causale_codice: Mapped[str | None] = mapped_column(ForeignKey("causale_fermo.codice"))
    kwh: Mapped[Decimal]
    tempo_ciclo_medio_s: Mapped[Decimal | None]
    fonte: Mapped[str] = mapped_column(default="generatore")
    ricevuta_il: Mapped[datetime] = mapped_column(server_default=func.now())


class ProduzioneGiornaliera(Base):
    __tablename__ = "produzione_giornaliera"

    data: Mapped[date] = mapped_column(primary_key=True)
    macchina_id: Mapped[int] = mapped_column(ForeignKey("macchina.id"), primary_key=True)
    t_disp_s: Mapped[int]
    t_man_s: Mapped[int]
    t_fermo_s: Mapped[int]
    t_funz_s: Mapped[int]
    n_tot: Mapped[int]
    n_scarti: Mapped[int]
    kwh: Mapped[Decimal]
    ultima_rilevazione: Mapped[datetime | None]
    parziale: Mapped[bool] = mapped_column(default=False)


class Parametro(Base):
    __tablename__ = "parametro"

    chiave: Mapped[str] = mapped_column(primary_key=True)
    valore: Mapped[Decimal]
    unita: Mapped[str]
    descrizione: Mapped[str]


class Soglia(Base):
    __tablename__ = "soglia"

    id: Mapped[int] = mapped_column(primary_key=True)
    kpi: Mapped[str]
    ambito: Mapped[str]
    verso: Mapped[str]
    valore: Mapped[Decimal]


class Indicatore(Base):
    __tablename__ = "indicatore"

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[date]
    linea_id: Mapped[int | None] = mapped_column(ForeignKey("linea.id"))
    macchina_id: Mapped[int | None] = mapped_column(ForeignKey("macchina.id"))
    n_tot: Mapped[int]
    n_buoni: Mapped[int]
    n_scarti: Mapped[int]
    produttivita_conf_h: Mapped[Decimal | None]
    disponibilita: Mapped[Decimal | None]
    prestazioni: Mapped[Decimal | None]
    qualita: Mapped[Decimal | None]
    oee: Mapped[Decimal | None]
    tasso_scarto: Mapped[Decimal | None]
    kwh: Mapped[Decimal]
    kwh_conf: Mapped[Decimal | None]
    costo_fermi_eur: Mapped[Decimal]
    co2_kg: Mapped[Decimal]
    co2_kg_conf: Mapped[Decimal | None]
    saturazione: Mapped[Decimal | None]
    costo_macchina_eur: Mapped[Decimal]
    costo_energia_eur: Mapped[Decimal]
    costo_materia_eur: Mapped[Decimal]
    costo_totale_eur: Mapped[Decimal]
    costo_unitario_eur: Mapped[Decimal | None]
    costo_scarti_eur: Mapped[Decimal]
    parziale: Mapped[bool] = mapped_column(default=False)
    calcolato_il: Mapped[datetime] = mapped_column(server_default=func.now())


class Anomalia(Base):
    __tablename__ = "anomalia"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str]
    data: Mapped[date]
    macchina_id: Mapped[int | None] = mapped_column(ForeignKey("macchina.id"))
    inizio: Mapped[datetime | None]
    fine: Mapped[datetime | None]
    causale_codice: Mapped[str | None] = mapped_column(ForeignKey("causale_fermo.codice"))
    kpi: Mapped[str | None]
    valore: Mapped[Decimal | None]
    soglia: Mapped[Decimal | None]
    descrizione: Mapped[str]
