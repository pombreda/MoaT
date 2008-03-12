/*
 *  Copyright © 2008, Matthias Urlichs <matthias@urlichs.de>
 *
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License (included; see the file LICENSE)
 *  for more details.
 */

/*
 * Main code.
 */

#include <avr/pgmspace.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "uart.h"
#include "qtask.h"
#include "qdelay.h"
#include "util.h"
#include "flow_data.h"

unsigned long run = 0;
unsigned int ping_timer = 1;

void runit1(task_head *dummy);

task_head idle_task = TASK_HEAD(runit1);

void runit1(task_head *dummy) {
	char buf[9];
	++run;
	fputc('P',stderr);
	ltoa(run,buf,16);
	if(strlen(buf)&1)
		fputc('0',stderr);
	fputs(buf,stderr);
	fputc('\r',stderr);
	queue_task_sec(&idle_task,ping_timer);
}

inline void set_ping(write_head *cb)
{
	unsigned int pingtimer = 0;
	unsigned char *bp = cb->data;
	if(cb->len < 1 || cb->len > 2) {
		fputs_P(PSTR("-Bad length\n"),stderr);
	} else {
		while(cb->len--)
			pingtimer = (pingtimer<<8) | (*bp++);
		if(pingtimer) {
			char buf[10];
			ping_timer = pingtimer;
			fputs_P(PSTR("+OK, ping "),stderr);
			fputs(itoa(pingtimer,buf,10),stderr);
			fputc('\n',stderr);
		} else
			fputs_P(PSTR("-Zero\n"),stderr);
		ping_timer = pingtimer;
	}
	free(cb);
}

void line_reader(task_head *tsk)
{
	unsigned char *rp = (unsigned char *)(tsk+1);
	//fprintf_P(stderr,PSTR(":IN: <%s>\n"),rp);
	fputs_P(PSTR(":IN: <"),stderr);
	fputs((char *)rp,stderr);
	fputs_P(PSTR(">\n"),stderr);
	if(!*rp) goto out;

	write_head *cb = malloc(sizeof(write_head)+((strlen((char *)rp)-1)>>1));
	if(!cb)
		report_error("out of memory");
	cb->type = *rp++;
	cb->next = NULL;
	unsigned char *wp = cb->data;
	
	unsigned char part = 0;
	unsigned char nibble=0;
	while(*rp) {
		if(*rp >= '0' && *rp <= '9') {
			part |= *rp++ - '0';
		} else if(*rp >= 'a' && *rp <= 'f') {
			part |= *rp++ - 'a' + 10;
		} else if(*rp >= 'A' && *rp <= 'F') {
			part |= *rp++ - 'A' + 10;
		} else {
			char buf[3];
			fputs_P(PSTR("-Unknown hex char 0x"),stderr);
			fputs(itoa(*rp,buf,16),stderr);
			fputc('\n',stderr);
			goto out;
		}
		if (++nibble&1) {
			part <<= 4;
		} else {
			*wp++ = part;
			part = 0;
		}
	}
	if(nibble&1) {
		fputs_P(PSTR("-Odd string length!\n"),stderr);
		goto out;
	}
	cb->len = nibble>>1;
	switch(cb->type) {
	case 'P':
		set_ping(cb);
		break;
	default:
		send_tx(cb);
		break;
	}

out:
	free(tsk);
	return;
}

void read_response(task_head *task)
{
	unsigned char *buf = (unsigned char *)(task+1);
	unsigned char type = *buf++;
	unsigned char len = *buf++;

	DBGS("Data! %c:%d",type,len);
	uart_putc(type);
	while(len--)
		uart_puthex_byte(*buf++);
	uart_putc('\n');
	free(task);
}

int __attribute__((noreturn)) main(void)
{
	extern void rx_chain();
	rx_chain();

	setup_stdio();
	fputs_P(PSTR(":Startup\n"),stderr);

	queue_task_sec(&idle_task,1);
#ifdef SLOW
	extern task_head tx_clock;
	queue_task_msec(&tx_clock,10);
#endif

#if 0
	unsigned char opb;
	unsigned char ota;
	unsigned char otb;
	unsigned char otc;
#endif
	PORTB=0xFF;
	
	while(1) {
#if 0
		unsigned char pb = PINB;
		unsigned char ta = TCCR1A;
		unsigned char tb = TCCR1B;
		unsigned char tc = TCCR1C;
		if((pb != opb) || (ta != ota) || (tb != otb) || (tc != otc)) {
			printf_P(PSTR("Port B:%02x tcc1:%02x %02x %02x\n"),pb,ta,tb,tc);
			opb = pb; ota = ta; otb = tb; otc = tc;
		}
#endif
		run_tasks();
	}
}
