import { ArrowRight } from 'lucide-react'
import Image from 'next/image'
import Link from 'next/link'
import learnhouseIcon from 'public/black_logo.png'

export default function NotFound() {
  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-center bg-background">
      <div className="nx-flex nx-items-center hover:nx-opacity-75 ltr:nx-mr-auto rtl:nx-ml-auto pb-20">
        <Image
          quality={100}
          width={270}
          height={100}
          src={learnhouseIcon}
          alt="logo"
          className="dark:invert"
        />
      </div>
      <div className="space-y-6 text-center">
        <h1 className="text-8xl leading-7 font-bold text-foreground drop-shadow-md">
          404!
        </h1>
        <p className="text-lg pt-8 text-foreground tracking-tight font-medium leading-normal">
          We are very sorry for the inconvenience. It looks like you're trying to
          <div>access a page that has been deleted or never existed before</div>
        </p>
      </div>
      <div className="pt-8 flex flex-col items-center">
        <button className="flex w-fit h-[50px] text-xl space-x-2 bg-primary px-6 py-2 text-md rounded-lg font-bold text-primary-foreground items-center shadow-md hover:opacity-90 transition-opacity">
          <Link className="flex gap-2" href="/">
            Go back to homepage
            <ArrowRight className='tracking-tight group-hover:translate-x-0.5 
        transition-transform duration-150 ease-in-out ml-1' />
          </Link>
        </button>
      </div>
    </div>
  )
}

